$ErrorActionPreference = "Stop"
$token = "vca_5vYxPxBDVwaBaqaX59bxCeaLn5sCMtSaJj0CCe8nUvXcucUy2b1WPE4T"
$teamId = "team_Hi3HDetItAIzr9hFbwgS8Ndk"
$projectName = "fruit-quality-ai"
$root = "c:\Users\Madhurendra bharti\OneDrive\Documents\Desktop\FruitQualityAI"
$headers = @{
    "Authorization" = "Bearer $token"
    "Accept"        = "application/json"
}
function hdr_json { return @{ Authorization = $headers.Authorization; Accept="application/json"; "Content-Type"="application/json" } }

Write-Host "=== Step 1: List projects on personal team ==="
try {
    $list = Invoke-RestMethod "https://api.vercel.com/v9/projects?teamId=$teamId&limit=20" -Headers $headers -Method Get
    $existing = $list.projects | Where-Object { $_.name -eq $projectName } | Select-Object -First 1
    if ($existing) {
        Write-Host "  Project EXISTS: id=$($existing.id)"
        $projectId = $existing.id
    } else {
        Write-Host "  Project does not exist; creating..."
        $body = @{
            name = $projectName
            framework = $null
            installCommand = "cd frontend && npm install && cd .. && pip install -r requirements.txt --quiet"
            buildCommand = "cd frontend && npx vite build --outDir dist"
            outputDirectory = "frontend/dist"
            devCommand = $null
            commandForIgnoringBuildStep = $null
            publicSource = $false
            serverlessFunctionRegion = "bom1"
            nodeVersion = "20.x"
        } | ConvertTo-Json -Depth 10
        $new = Invoke-RestMethod "https://api.vercel.com/v10/projects?teamId=$teamId" -Headers (hdr_json) -Method Post -Body $body
        Write-Host "  Project CREATED: id=$($new.id)"
        $projectId = $new.id
    }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  BODY: $($sr.ReadToEnd())"
    }
    exit 1
}
Write-Host "  Final projectId=$projectId"
Write-Host ""

Write-Host "=== Step 2: Apply vercel.json settings to project (rewrites, functions) ==="
$vercelJson = Get-Content (Join-Path $root "vercel.json") -Raw | ConvertFrom-Json
Write-Host "  Installing vercel.json rewrites..."
try {
    $patch = @{
        name = $projectName
        framework = $null
        installCommand = $vercelJson.installCommand
        buildCommand = $vercelJson.buildCommand
        outputDirectory = $vercelJson.outputDirectory
        devCommand = $null
    } | ConvertTo-Json -Depth 10
    Invoke-RestMethod "https://api.vercel.com/v9/projects/$projectId?teamId=$teamId" -Headers (hdr_json) -Method Patch -Body $patch | Out-Null
    Write-Host "  Project build settings patched."
} catch {
    Write-Host "  WARN project patch failed: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  BODY: $($sr.ReadToEnd())"
    }
}
Write-Host ""

Write-Host "=== Step 3: Compute list of files to upload, respecting .vercelignore ==="
$ignoreLines = Get-Content (Join-Path $root ".vercelignore") | Where-Object { $_ -notmatch "^\s*#" -and $_.Trim() -ne "" } | ForEach-Object { $_.Trim() }
function IsIgnored([string]$relative) {
    $norm = $relative.Replace("\", "/")
    foreach ($pat in $ignoreLines) {
        $p = $pat.TrimEnd("/", "*")
        $p = $p.Replace(".", "\.").Replace("*", ".*").Replace("?", ".?")
        try {
            if ($norm -match "(^|/)$p") { return $true }
            if ($norm -match "^$p") { return $true }
        } catch {}
    }
    return $false
}
$allFiles = Get-ChildItem $root -Recurse -File -Force -ErrorAction SilentlyContinue
$uploadFiles = @()
foreach ($f in $allFiles) {
    $rel = $f.FullName.Substring($root.Length).TrimStart("\", "/")
    if (IsIgnored $rel) { continue }
    # Double check safety filters
    if ($rel.StartsWith(".venv") -or $rel.StartsWith("backend\.venv") -or $rel.StartsWith("backend\venv") -or `
        $rel.StartsWith("FruitNet") -or $rel.StartsWith("node_modules") -or $rel.StartsWith("frontend\node_modules") -or `
        $rel.StartsWith("frontend\dist") -or $rel.StartsWith("__pycache__") -or $rel.Contains("__pycache__") -or `
        $rel.EndsWith(".pyc") -or $rel.EndsWith(".pyo") -or $rel.EndsWith(".pyd") -or $rel.EndsWith(".db") -or `
        $rel -eq "backend\.env" -or $rel -eq ".env" -or $rel -eq ".env.local" -or `
        $rel.StartsWith(".git\") -or $rel -eq ".vercelignore" -or $rel.StartsWith(".trae\") -or `
        $rel.StartsWith("_test_") -or $rel.StartsWith("_vercel_") -or $rel.StartsWith(".temp-") -or $rel.StartsWith(".tmp-")) {
        continue
    }
    $uploadFiles += [PSCustomObject]@{ Path = $rel.Replace("\", "/"); Full = $f.FullName; Length = $f.Length }
}
Write-Host "  Total files to upload: $($uploadFiles.Count)"
$totalBytes = ($uploadFiles | Measure-Object -Property Length -Sum).Sum
Write-Host ("  Total size: {0:N2} KB" -f ($totalBytes / 1024))
$uploadFiles | Select-Object -First 40 | ForEach-Object { Write-Host "    - $($_.Path) ($($_.Length) bytes)" }
Write-Host ""

Write-Host "=== Step 4: Create a deployment (POST /v13/deployments) ==="
try {
    $filesPayload = @()
    foreach ($f in $uploadFiles) {
        $sha = (Get-FileHash -Path $f.Full -Algorithm SHA1).Hash.ToLower()
        $filesPayload += [PSCustomObject]@{
            file = $f.Path
            data = [System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes($f.Full))
            encoding = "base64"
        }
    }
    $deplPayload = @{
        name = $projectName
        project = $projectName
        target = "production"
        files = $filesPayload
        functions = @{
            "api/index.py" = @{ runtime = "python@3.12" }
            "api/[...path].py" = @{ runtime = "python@3.12" }
        }
        regions = @("bom1")
        framework = $null
        build = @{
            env = @{ VERCEL_TELEMETRY_DISABLED = "1" }
        }
    }
    $bodyStr = $deplPayload | ConvertTo-Json -Depth 30 -Compress
    Write-Host "  JSON payload size: $($bodyStr.Length) chars"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($bodyStr)
    Write-Host "  Creating deployment via REST API..."
    $resp = Invoke-RestMethod "https://api.vercel.com/v13/deployments?teamId=$teamId&skipAutoFetch=1&forceNew=1" -Headers (hdr_json) -Method Post -Body $bytes
    Write-Host "  Deployment UID: $($resp.uid)"
    Write-Host "  Deployment URL: https://$($resp.url)"
    Write-Host "  Ready state: $($resp.readyState)"
    Write-Host "  Alias (target production): $($resp.alias -join ', ')"
    $deplId = $resp.uid
    $deplUrl = $resp.url
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  BODY: $($sr.ReadToEnd())"
    }
    exit 1
}
Write-Host ""

Write-Host "=== Step 5: Poll deployment until readyState is READY or ERROR (max 25 mins) ==="
$deadline = (Get-Date).AddMinutes(25)
$sleepSec = 15
do {
    Start-Sleep -Seconds $sleepSec
    try {
        $poll = Invoke-RestMethod "https://api.vercel.com/v13/deployments/$deplId?teamId=$teamId" -Headers $headers -Method Get
        $state = $poll.readyState
        Write-Host "  $(Get-Date -Format 'HH:mm:ss') state=$state  url=https://$($poll.url)"
        if ($poll.errorCode -or $poll.errorMessage) {
            Write-Host "    ERROR CODE: $($poll.errorCode)"
            Write-Host "    ERROR MSG : $($poll.errorMessage)"
            if ($poll.errorLink) { Write-Host "    SEE: $($poll.errorLink)" }
        }
        if ($state -eq "READY") {
            Write-Host "  SUCCESS - Deployment built and promoted."
            break
        }
        if ($state -eq "ERROR" -or $state -eq "CANCELED") {
            Write-Host "  FAILURE - Deployment did not build successfully."
            # Try fetching build events
            try {
                $ev = Invoke-RestMethod "https://api.vercel.com/v2/deployments/$deplId/builds?teamId=$teamId" -Headers $headers -Method Get
                Write-Host "  Build sub-entries:"
                foreach ($b in $ev.builds) {
                    Write-Host "    state=$($b.state)  entrypoint=$($b.entrypoint)  path=$($b.path)"
                    if ($b.errorMessage -or $b.errorCode) { Write-Host "     err=$($b.errorCode): $($b.errorMessage)" }
                }
            } catch {}
            exit 1
        }
    } catch {
        Write-Host "  (poll warning: $($_.Exception.Message))"
    }
    if ($sleepSec -lt 45) { $sleepSec += 5 }
} while ((Get-Date) -lt $deadline)
Write-Host ""
Write-Host "=== DONE ==="
Write-Host "  Deployment ID: $deplId"
Write-Host "  Production URL: https://$deplUrl"
Write-Host "  Alias:  https://$projectName.vercel.app"
