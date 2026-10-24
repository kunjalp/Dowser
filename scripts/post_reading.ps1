# Smoke-test the ingest endpoint on Windows PowerShell.
#   $env:CONVEX_SITE_URL = "https://<deployment>.convex.site"   # .site, not .cloud
#   $env:INGEST_TOKEN    = "<token>"
#   .\scripts\post_reading.ps1 [-Value 12] [-Raw 512]
param([double]$Value = 12, [double]$Raw = 512)
$site = $env:CONVEX_SITE_URL; $token = $env:INGEST_TOKEN
if (-not $site -or -not $token) { throw "Set CONVEX_SITE_URL and INGEST_TOKEN first." }

"health:"; Invoke-RestMethod "$site/health"
"reading:"
$body = @{ deviceId = "esp32-test"; value = $Value; raw = $Raw; isReplay = $true
           timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() } | ConvertTo-Json
Invoke-RestMethod -Method Post "$site/ingest/reading" -Headers @{ "X-Dowser-Token" = $token } `
  -ContentType "application/json" -Body $body
"bad token (expect 401):"
try { Invoke-RestMethod -Method Post "$site/ingest/reading" -Headers @{ "X-Dowser-Token" = "wrong" } -Body "{}" }
catch { $_.Exception.Response.StatusCode.value__ }
