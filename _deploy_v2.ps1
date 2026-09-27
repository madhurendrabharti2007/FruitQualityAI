$ErrorActionPreference = "Stop"
$token = "vca_5vYxPxBDVwaBaqaX59bxCeaLn5sCMtSaJj0CCe8nUvXcucUy2b1WPE4T"
$teamId = "team_Hi3HDetItAIzr9hFbwgS8Ndk"
$projectId = "prj_bsNp8EuBos9b6Cj22YDqUJVGhEEu"
$projectName = "fruit-quality-ai"
$root = "c:\Users\Madhurendra bharti\OneDrive\Documents\Desktop\FruitQualityAI"
$headers_json = @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json"
    "Accept"        = "application/json"
}
$headers = @{
    "Authorization" = "Bearer $token"
    "Accept"        = "application/json"
}

Write-Host "=== Step 1: Configure project build settings from vercel.json ==="
try {
    $vercelJson = Get-Content (Join-Path $root "vercel.json") -Raw | ConvertFrom-Json
    $patch = @{
        name = $projectName
        installCommand = $vercelJson.installCommand
        buildCommand = $vercelJson.buildCommand
        outputDirectory = $vercelJson.outputDirectory
    } | ConvertTo-Json -Depth 5
    Invoke-RestMethod "https://api.vercel.com/v9/projects/$projectId?teamId=$teamId" -Headers $headers_json -Method Patch -Body $patch | Out-Null
    Write-Host "  OK - Project build settings applied"
} catch {
    Write-Host "  WARN: $($_.Exception.Message)"
}

Write-Host "=== Step 2: Compute file list (respect .vercelignore) ==="
$ignoreLines = Get-Content (Join-Path $root ".vercelignore") | Where-Object { $_ -notmatch "^\s*#" -and $_.Trim() -ne "" } | ForEach-Object { $_.Trim() }
function IsIgnored([string]$relative) {
    $norm = $relative.Replace("\", "/")
    # Explicit safe filters first
    if ($norm.StartsWith(".venv/") -or $norm.StartsWith("backend/.venv/") -or $norm.StartsWith("backend/venv/") -or `
        $norm.StartsWith("FruitNet") -or $norm.StartsWith("node_modules/") -or $norm.StartsWith("frontend/node_modules/") -or `
        $norm.StartsWith("frontend/dist/") -or $norm.Contains("/__pycache__/") -or $norm.StartsWith("__pycache__/") -or `
        $norm -match "\.py[cod]$" -or $norm -match "\.(db|sqlite|sqlite3)$" -or `
        $norm -eq "backend/.env" -or $norm -eq ".env" -or $norm -eq ".env.local" -or `
        $norm.StartsWith(".git/") -or $norm.StartsWith(".trae/") -or `
        $norm -like "_test_*" -or $norm -like "_vercel_*" -or `
        $norm -like "_deploy_vercel*" -or $norm -like "_debug_*" -or `
        $norm.StartsWith(".temp-") -or $norm.StartsWith(".tmp-") -or $norm.StartsWith(".tmp-cli/") -or `
        $norm.StartsWith("backend/dataset/") -or $norm.StartsWith("backend/uploads/") -or `
        $norm -match "^test_[a-z_]+\.(jpg|jpeg|png)$" -or `
        $norm -match "\.(log|bak|backup|orig)$" -or `
        $norm -like "api/__pycache__/*") {
        return $true
    }
    foreach ($pat in $ignoreLines) {
        if ($pat -match "^\.env$|^\.env\.|^Dockerfile|^README\.md|^requirements\.txt|^vercel\.json|^\.gitignore|^\.vercelignore") {
            # Only exact-match or .env.* - don't blanket wildcard
            if ($norm -eq $pat) { return $true }
            if ($pat -like ".env.*" -and $norm -like ".env.*" -and $norm -ne ".env.example" -and $norm -ne "backend/.env.example") { return $true }
        }
        $p = $pat
        foreach ($suffix in @("/", "/*", "/**", "/**/*")) { if ($p.EndsWith($suffix)) { $p = $p.Substring(0, $p.Length - $suffix.Length) } }
        $pEsc = [regex]::Escape($p).Replace("\*", ".*").Replace("\?", ".?")
        try {
            if ($norm -match "(^|/)$pEsc($|/)") { return $true }
        } catch {}
    }
    return $false
}
$allFiles = Get-ChildItem $root -Recurse -File -Force -ErrorAction SilentlyContinue
$uploadFiles = @()
foreach ($f in $allFiles) {
    $rel = $f.FullName.Substring($root.Length).TrimStart("\", "/")
    if (IsIgnored $rel) { continue }
    $unix = $rel.Replace("\", "/")
    $uploadFiles += [PSCustomObject]@{ Path = $unix; Full = $f.FullName; Length = $f.Length }
}
$totalBytes = ($uploadFiles | Measure-Object -Property Length -Sum).Sum
Write-Host "  Uploading $($uploadFiles.Count) files, $([math]::Round($totalBytes/1024,2)) KB"
$uploadFiles | ForEach-Object { Write-Host "    - $($_.Path) ($($_.Length) b)" }

Write-Host "=== Step 3: Create deployment via POST /v13/deployments ==="
$filesPayload = @()
foreach ($f in $uploadFiles) {
    $sha = (Get-FileHash -Path $f.Full -Algorithm SHA1).Hash.ToLower()
    $bytes = [System.IO.File]::ReadAllBytes($f.Full)
    $filesPayload += [ordered]@{
        file = $f.Path
        data = [System.Convert]::ToBase64String($bytes)
        encoding = "base64"
        sha  = $sha
        size = $bytes.Length
    }
}
$depl = [ordered]@{
    name = $projectName
    target = "production"
    files = $filesPayload
}
$bodyJson = $depl | ConvertTo-Json -Depth 10 -Compress
Write-Host "  Payload: $($bodyJson.Length) chars; posting..."
try {
    $resp = Invoke-RestMethod "https://api.vercel.com/v13/deployments?teamId=$teamId&forceNew=1" -Headers $headers_json -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($bodyJson))
    Write-Host "  Deployment UID: $($resp.uid)"
    Write-Host "  URL:            https://$($resp.url)"
    Write-Host "  Ready state:    $($resp.readyState)"
    $deplId = $resp.uid
    $deplUrl = $resp.url
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)"
    $raw = $_.Exception.Response
    if ($raw) {
        $rs = $raw.GetResponseStream()
        $buf = New-Object byte[] (64 * 1024)
        $n = $rs.Read($buf, 0, $buf.Length)
        $bStr = [System.Text.Encoding]::UTF8.GetString($buf, 0, $n)
        Write-Host "  STATUS: $([int]$raw.StatusCode)"
        Write-Host "  BODY: $bStr"
    }
    exit 1
}

Write-Host ""
Write-Host "=== Step 4: Poll deployment (max 30 min) ==="
$deadline = (Get-Date).AddMinutes(30)
$sleep = 10
do {
    Start-Sleep -Seconds $sleep
    try {
        $poll = Invoke-RestMethod "https://api.vercel.com/v13/deployments/$deplId?teamId=$teamId" -Headers $headers -Method Get
        $st = $poll.readyState
        Write-Host "  $(Get-Date -Format 'HH:mm:ss') state=$st  aliasAssigned=$($poll.aliasAssigned)"
        if ($poll.errorCode) { Write-Host "    errorCode=$($poll.errorCode) msg=$($poll.errorMessage)" }
        if ($st -eq "READY") { Write-Host "  Build succeeded!"; break }
        if ($st -eq "ERROR" -or $st -eq "CANCELED") {
            Write-Host "  Build FAILED. Fetching build events..."
            try {
                $ev = Invoke-RestMethod "https://api.vercel.com/v2/deployments/$deplId/builds?teamId=$teamId" -Headers $headers -Method Get
                foreach ($b in $ev.builds) {
                    Write-Host "    entry=$($b.entrypoint) state=$($b.state) code=$($b.errorCode) msg=$($b.errorMessage)"
                }
            } catch { Write-Host "    (could not fetch build events: $($_.Exception.Message))" }
            exit 1
        }
    } catch {
        Write-Host "  (poll retry: $($_.Exception.Message))"
    }
    if ($sleep -lt 40) { $sleep += 3 }
} while ((Get-Date) -lt $deadline)
Write-Host ""
Write-Host "=== Step 5: Project aliases ==="
try {
    $aliases = Invoke-RestMethod "https://api.vercel.com/v9/projects/$projectId/aliases?teamId=$teamId" -Headers $headers -Method Get
    foreach ($a in $aliases.aliases) { Write-Host "  - https://$($a.alias) (deployment $($a.deploymentId))" }
} catch {}
Write-Host ""
Write-Host "FINAL RESULT:"
Write-Host "  Deployment ID : $deplId"
Write-Host "  Project ID    : $projectId"
Write-Host "  Deployment URL: https://$deplUrl"
Write-Host "  Production URL: https://$projectName.vercel.app"
