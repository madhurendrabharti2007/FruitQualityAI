$token = "vca_5vYxPxBDVwaBaqaX59bxCeaLn5sCMtSaJj0CCe8nUvXcucUy2b1WPE4T"
$teamId = "team_PMfoTB66mteLcrYLC5FlS1ih"
$projectName = "fruit-quality-ai"
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json"
    "Accept"        = "application/json"
}
Write-Host "=== Listing 10 latest deployments for $projectName (team $teamId) ==="
try {
    $url = "https://api.vercel.com/v6/deployments?projectId=$projectName&teamId=$teamId&limit=10"
    $resp = Invoke-RestMethod -Uri $url -Method Get -Headers $headers
    if ($resp.deployments) {
        foreach ($d in $resp.deployments) {
            $ts = [DateTimeOffset]::FromUnixTimeMilliseconds($d.createdAt).LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss")
            Write-Host "  [$($d.state.ToUpper())] $ts  url=$($d.url)  id=$($d.uid)  target=$($d.target)  readyState=$($d.readyState)"
        }
    } else {
        Write-Host "  (no deployments found via projectId=$projectName; trying alternate endpoint...)"
    }
} catch {
    Write-Host "  Request failed: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $body = $sr.ReadToEnd()
        Write-Host "  Response body: $body"
    }
}
Write-Host ""
Write-Host "=== Checking deployments via /v5/deployments (no project filter) ==="
try {
    $url = "https://api.vercel.com/v5/now/deployments?teamId=$teamId&limit=10"
    $resp = Invoke-RestMethod -Uri $url -Method Get -Headers $headers
    foreach ($d in $resp.deployments) {
        $ts = [DateTimeOffset]::FromUnixTimeMilliseconds($d.createdAt).LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss")
        Write-Host "  [$($d.state.ToUpper())] $ts  name=$($d.name)  url=$($d.url)  id=$($d.uid)"
    }
} catch {
    Write-Host "  Request failed: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $body = $sr.ReadToEnd()
        Write-Host "  Response body: $body"
    }
}
Write-Host ""
Write-Host "=== Getting specific deployment D29LhZSdCr1DUwmfao2yWvLRcbX4 (with fixes) ==="
try {
    $url = "https://api.vercel.com/v13/deployments/D29LhZSdCr1DUwmfao2yWvLRcbX4?teamId=$teamId"
    $resp = Invoke-RestMethod -Uri $url -Method Get -Headers $headers
    Write-Host "  url:        $($resp.url)"
    Write-Host "  name:       $($resp.name)"
    Write-Host "  state:      $($resp.state)"
    Write-Host "  readyState: $($resp.readyState)"
    Write-Host "  target:     $($resp.target)"
    Write-Host "  createdAt:  $([DateTimeOffset]::FromUnixTimeMilliseconds($resp.createdAt).LocalDateTime)"
    if ($resp.errorCode) { Write-Host "  errorCode:  $($resp.errorCode)" }
    if ($resp.errorMessage) { Write-Host "  errorMsg:   $($resp.errorMessage)" }
    if ($resp.errorLink) { Write-Host "  errorLink:  $($resp.errorLink)" }
} catch {
    Write-Host "  Request failed: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $body = $sr.ReadToEnd()
        Write-Host "  Response body: $body"
    }
}
Write-Host ""
Write-Host "=== Getting specific deployment CXHWdu2uhPC54Sh4wULvHDhAeJkp (first build) ==="
try {
    $url = "https://api.vercel.com/v13/deployments/CXHWdu2uhPC54Sh4wULvHDhAeJkp?teamId=$teamId"
    $resp = Invoke-RestMethod -Uri $url -Method Get -Headers $headers
    Write-Host "  url:        $($resp.url)"
    Write-Host "  state:      $($resp.state)"
    Write-Host "  readyState: $($resp.readyState)"
    Write-Host "  target:     $($resp.target)"
    if ($resp.errorCode) { Write-Host "  errorCode:  $($resp.errorCode)" }
    if ($resp.errorMessage) { Write-Host "  errorMsg:   $($resp.errorMessage)" }
} catch {
    Write-Host "  Request failed: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $body = $sr.ReadToEnd()
        Write-Host "  Response body: $body"
    }
}
Write-Host ""
Write-Host "=== Fetching build events for D29LhZSdCr1DUwmfao2yWvLRcbX4 ==="
try {
    $url = "https://api.vercel.com/v2/deployments/D29LhZSdCr1DUwmfao2yWvLRcbX4/builds?teamId=$teamId"
    $resp = Invoke-RestMethod -Uri $url -Method Get -Headers $headers
    foreach ($b in $resp.builds) {
        Write-Host "  Build entry: id=$($b.id) state=$($b.state) entrypoint=$($b.entrypoint)"
        if ($b.errorCode) { Write-Host "    errorCode:  $($b.errorCode)" }
        if ($b.errorMessage) { Write-Host "    errorMsg:   $($b.errorMessage)" }
    }
} catch {
    Write-Host "  Request failed: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $body = $sr.ReadToEnd()
        Write-Host "  Response body: $body"
    }
}
Write-Host ""
Write-Host "=== Inspect Project details ==="
try {
    $url = "https://api.vercel.com/v9/projects/$projectName?teamId=$teamId"
    $resp = Invoke-RestMethod -Uri $url -Method Get -Headers $headers
    Write-Host "  projectId: $($resp.id)"
    Write-Host "  framework: $($resp.framework)"
    Write-Host "  buildCommand: $($resp.buildCommand)"
    Write-Host "  installCommand: $($resp.installCommand)"
    Write-Host "  devCommand: $($resp.devCommand)"
    Write-Host "  outputDirectory: $($resp.outputDirectory)"
    Write-Host "  nodeVersion: $($resp.nodeVersion)"
    Write-Host "  autoExposeSystemEnvVars: $($resp.autoExposeSystemEnvVars)"
    Write-Host "  latestDeployments:"
    foreach ($ld in $resp.latestDeployments | Select-Object -First 5) {
        Write-Host "    - uid=$($ld.uid) state=$($ld.state) readyState=$($ld.readyState) url=$($ld.url)"
    }
} catch {
    Write-Host "  Request failed: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $body = $sr.ReadToEnd()
        Write-Host "  Response body: $body"
    }
}
