$token = "vca_5vYxPxBDVwaBaqaX59bxCeaLn5sCMtSaJj0CCe8nUvXcucUy2b1WPE4T"
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json"
}
Write-Host "=== GET /v2/user (authenticated user info) ==="
try {
    $resp = Invoke-RestMethod -Uri "https://api.vercel.com/v2/user" -Method Get -Headers $headers
    Write-Host "  uid:        $($resp.user.uid)"
    Write-Host "  email:      $($resp.user.email)"
    Write-Host "  username:   $($resp.user.username)"
    Write-Host "  name:       $($resp.user.name)"
    Write-Host "  billing.type: $($resp.billing.type)"
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  BODY: $($sr.ReadToEnd())"
    }
}
Write-Host ""
Write-Host "=== GET /v2/teams (what teams does user belong to?) ==="
try {
    $resp = Invoke-RestMethod -Uri "https://api.vercel.com/v2/teams" -Method Get -Headers $headers
    Write-Host "  Total: $($resp.teams.Count) teams"
    foreach ($t in $resp.teams) {
        Write-Host "  - id=$($t.id)  slug=$($t.slug)  name=$($t.name)  role=$($t.role)"
    }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  BODY: $($sr.ReadToEnd())"
    }
}
Write-Host ""
Write-Host "=== GET /v9/projects (list all user's projects, no teamId param first) ==="
try {
    $resp = Invoke-RestMethod -Uri "https://api.vercel.com/v9/projects?limit=10" -Method Get -Headers $headers
    Write-Host "  Total: $($resp.projects.Count) projects"
    foreach ($p in $resp.projects) {
        Write-Host "  - id=$($p.id)  name=$($p.name)  accountId=$($p.accountId)  latestDeployCount=$($p.latestDeployments.Count)"
        foreach ($ld in $p.latestDeployments | Select-Object -First 2) {
            Write-Host "     latest uid=$($ld.uid) state=$($ld.state) readyState=$($ld.readyState) url=$($ld.url)"
        }
    }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  BODY: $($sr.ReadToEnd())"
    }
}
Write-Host ""
Write-Host "=== GET /v9/projects with teamId=team_PMfoTB66mteLcrYLC5FlS1ih ==="
try {
    $resp = Invoke-RestMethod -Uri "https://api.vercel.com/v9/projects?limit=10&teamId=team_PMfoTB66mteLcrYLC5FlS1ih" -Method Get -Headers $headers
    Write-Host "  Total: $($resp.projects.Count) projects"
    foreach ($p in $resp.projects) {
        Write-Host "  - id=$($p.id)  name=$($p.name)  accountId=$($p.accountId)"
        foreach ($ld in $p.latestDeployments | Select-Object -First 3) {
            Write-Host "     uid=$($ld.uid) state=$($ld.state) readyState=$($ld.readyState) url=$($ld.url) target=$($ld.target)"
        }
    }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  BODY: $($sr.ReadToEnd())"
    }
}
Write-Host ""
Write-Host "=== GET project by id=prj_2hkyntOyi5m7hpUiz9Un4SBFbrsk + teamId=team_PMfoTB66mteLcrYLC5FlS1ih ==="
try {
    $resp = Invoke-RestMethod -Uri "https://api.vercel.com/v9/projects/prj_2hkyntOyi5m7hpUiz9Un4SBFbrsk?teamId=team_PMfoTB66mteLcrYLC5FlS1ih" -Method Get -Headers $headers
    Write-Host "  id=$($resp.id)  name=$($resp.name)  fw=$($resp.framework)  bc=$($resp.buildCommand)  ic=$($resp.installCommand)  outDir=$($resp.outputDirectory)"
    Write-Host "  latestDeployments:"
    foreach ($ld in $resp.latestDeployments | Select-Object -First 5) {
        Write-Host "    uid=$($ld.uid)  state=$($ld.state)  readyState=$($ld.readyState)  target=$($ld.target)  url=$($ld.url)  creator=$($ld.creator.username)"
        if ($ld.errorCode) { Write-Host "      error=$($ld.errorCode): $($ld.errorMessage)" }
    }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  BODY: $($sr.ReadToEnd())"
    }
}
Write-Host ""
Write-Host "=== GET deployment D29LhZSdCr1DUwmfao2yWvLRcbX4 by id, with teamId=team_PMfoTB66mteLcrYLC5FlS1ih ==="
try {
    $resp = Invoke-RestMethod -Uri "https://api.vercel.com/v13/deployments/D29LhZSdCr1DUwmfao2yWvLRcbX4?teamId=team_PMfoTB66mteLcrYLC5FlS1ih" -Method Get -Headers $headers
    Write-Host "  url=$($resp.url)  state=$($resp.state)  readyState=$($resp.readyState)  target=$($resp.target)"
    Write-Host "  createdAt=$([DateTimeOffset]::FromUnixTimeMilliseconds($resp.createdAt).LocalDateTime)"
    if ($resp.errorCode) { Write-Host "  ERROR: code=$($resp.errorCode)  msg=$($resp.errorMessage)  link=$($resp.errorLink)" }
    if ($resp.buildErrorId) { Write-Host "  buildErrorId=$($resp.buildErrorId)" }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  BODY: $($sr.ReadToEnd())"
    }
}
Write-Host ""
Write-Host "=== GET deployment CXHWdu2uhPC54Sh4wULvHDhAeJkp by id, with teamId=team_PMfoTB66mteLcrYLC5FlS1ih ==="
try {
    $resp = Invoke-RestMethod -Uri "https://api.vercel.com/v13/deployments/CXHWdu2uhPC54Sh4wULvHDhAeJkp?teamId=team_PMfoTB66mteLcrYLC5FlS1ih" -Method Get -Headers $headers
    Write-Host "  url=$($resp.url)  state=$($resp.state)  readyState=$($resp.readyState)  target=$($resp.target)"
    if ($resp.errorCode) { Write-Host "  ERROR: code=$($resp.errorCode)  msg=$($resp.errorMessage)  link=$($resp.errorLink)" }
    if ($resp.buildErrorId) { Write-Host "  buildErrorId=$($resp.buildErrorId)" }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  BODY: $($sr.ReadToEnd())"
    }
}
