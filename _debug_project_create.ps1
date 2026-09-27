$ErrorActionPreference = "Stop"
$token = "vca_5vYxPxBDVwaBaqaX59bxCeaLn5sCMtSaJj0CCe8nUvXcucUy2b1WPE4T"
$teamId = "team_Hi3HDetItAIzr9hFbwgS8Ndk"
$projectName = "fruit-quality-ai"
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json"
    "Accept"        = "application/json"
}
Write-Host "=== Step 1: Try creating project with MINIMAL payload ==="
# Try different payload versions; record error body in full
$payloads = @(
    # Version A: absolute minimum
    @{ name = $projectName },
    # Version B: with null frameworks
    @{ name = $projectName; framework = $null },
    # Version C: with string framework empty
    @{ name = $projectName; environment = @{} }
)
for ($i = 0; $i -lt $payloads.Count; $i++) {
    $p = $payloads[$i] | ConvertTo-Json -Depth 10
    Write-Host "  Trying payload version $i..."
    try {
        $resp = Invoke-RestMethod "https://api.vercel.com/v10/projects?teamId=$teamId" -Headers $headers -Method Post -Body $p
        Write-Host "  SUCCESS. id=$($resp.id)  name=$($resp.name)  accountId=$($resp.accountId)"
        exit 0
    } catch {
        Write-Host "  payload $i failed: $($_.Exception.Message)"
        $raw = $_.Exception.Response
        if ($raw) {
            $statusCode = [int]$raw.StatusCode
            $rs = $raw.GetResponseStream()
            $buf = New-Object byte[] $raw.ContentLength
            if ($raw.ContentLength -gt 0) { [void]$rs.Read($buf, 0, [int]$raw.ContentLength) }
            $bodyStr = [System.Text.Encoding]::UTF8.GetString($buf)
            Write-Host "  STATUS: $statusCode"
            Write-Host "  BODY: $bodyStr"
        }
    }
    Write-Host ""
}
Write-Host "=== Step 2: Try v9/projects endpoint ==="
try {
    $p = (@{ name = $projectName } | ConvertTo-Json -Depth 5)
    $resp = Invoke-RestMethod "https://api.vercel.com/v9/projects?teamId=$teamId" -Headers $headers -Method Post -Body $p
    Write-Host "  v9 SUCCESS: id=$($resp.id)"
} catch {
    Write-Host "  v9 failed: $($_.Exception.Message)"
    $raw = $_.Exception.Response
    if ($raw) {
        $rs = $raw.GetResponseStream()
        $buf = New-Object byte[] $raw.ContentLength
        if ($raw.ContentLength -gt 0) { [void]$rs.Read($buf, 0, [int]$raw.ContentLength) }
        Write-Host "  BODY: $([System.Text.Encoding]::UTF8.GetString($buf))"
    }
}
