# Teacher Tool setup (Windows, PowerShell). Safe to re-run: keeps saved secrets unless you change them.
# Run from the repo folder:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Continue"  # native tools write progress to stderr; exit codes are checked instead
Set-Location $PSScriptRoot
function Step($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function Check($what) { if ($LASTEXITCODE -ne 0) { Write-Host "Failed: $what" -ForegroundColor Red; exit 1 } }

Step "1/6 Checking Docker"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker Desktop is not installed. Install it with:  winget install -e --id Docker.DockerDesktop" -ForegroundColor Yellow
  Write-Host "Then start Docker Desktop, wait for 'Engine running', and run this script again."; exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { Write-Host "Docker Desktop is installed but not running. Start it and re-run." -ForegroundColor Yellow; exit 1 }

Step "2/6 Building the tutor"
docker compose build api; Check "build"
# The setup wizard runs from its own image; rebuild it too or it keeps running an old copy (cached layers, so this is quick)
docker compose --profile setup build setup; Check "build setup"

# Remove any wizard container left over from an earlier, interrupted run
docker ps -aq --filter "name=teacher-tool-wizard-run" | ForEach-Object { docker rm -f $_ *> $null }

# Ports already published by other Docker containers (Windows doesn't always show these as listeners)
$dockerPorts = @(docker ps --format "{{.Ports}}" 2>$null | Select-String -Pattern ':(\d+)->' -AllMatches |
  ForEach-Object { $_.Matches } | ForEach-Object { [int]$_.Groups[1].Value })
if ($dockerPorts.Count) { Write-Host "Ports used by other containers: $($dockerPorts | Sort-Object -Unique)" }
function Get-FreePort([int]$start) {
  for ($p = $start; $p -lt $start + 50; $p++) {
    if ($dockerPorts -contains $p) { continue }
    if (-not (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)) { return $p }
  }
  throw "No free port near $start"
}
Step "3/6 Setup: answer the questions in this window (Claude login, speech, WhatsApp, checks)"
docker compose --profile setup run --rm setup; Check "setup"

$profiles = @()
if (Test-Path setup\profiles.txt) { Get-Content setup\profiles.txt | Where-Object { $_.Trim() } | ForEach-Object { $profiles += @("--profile", $_.Trim()) } }
$enabled = if (Test-Path setup\profiles.txt) { Get-Content setup\profiles.txt } else { @() }

Step "4/6 Starting services"
$ownApi = docker compose ps -q api 2>$null
if (-not $ownApi -and -not (Select-String -Path .env -Pattern '^TUTOR_PORT=' -Quiet) -and ((Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) -or ($dockerPorts -contains 8080))) {
  $tp = Get-FreePort 8081
  Write-Host "Port 8080 is busy; the tutor will use port $tp instead." -ForegroundColor Yellow
  Add-Content .env "TUTOR_PORT=$tp"
}
# OpenClaw runs as uid 1000 and can't use a Windows folder for its files, so its home is a Docker volume that is prepared first
if ($enabled -contains "whatsapp") { docker compose --profile whatsapp --profile whatsapp-cli run --rm openclaw-plugin-sync; Check "prepare OpenClaw volumes" }
docker compose @profiles up -d --build; Check "start services"

# The one-off OpenClaw commands share the gateway's network, which has no DNS while the gateway is starting or restarting
# (EAI_AGAIN on npm and WhatsApp), so wait until it reports healthy before each of them.
function Wait-Gateway {
  $id = docker compose --profile whatsapp ps -q openclaw-gateway 2>$null
  for ($i = 0; $id -and $i -lt 72; $i++) {
    if ((docker inspect -f "{{.State.Health.Status}}" $id 2>$null) -eq "healthy") { return }
    if ($i -eq 0) { Write-Host "Waiting for the OpenClaw gateway to start (up to 6 minutes)..." }
    Start-Sleep -Seconds 5
  }
  Write-Host "(the OpenClaw gateway is not healthy yet; carrying on)" -ForegroundColor Yellow
}

if ($enabled -contains "whatsapp") {
  Step "5/6 WhatsApp: installing the plugin and pairing"
  Wait-Gateway
  $cli = @("compose", "--profile", "whatsapp", "--profile", "whatsapp-cli", "run", "--rm", "openclaw-cli")
  # npm only (no ClawHub); Docker's DNS sometimes drops a lookup, so try a few times
  for ($i = 1; $i -le 3; $i++) {
    & docker @cli plugins install "npm:@openclaw/whatsapp" --force
    if ($LASTEXITCODE -eq 0) { break }
    if ($i -lt 3) { Write-Host "(attempt $i of 3 failed; trying again in 10 seconds)" -ForegroundColor Yellow; Start-Sleep -Seconds 10 }
  }
  if ($LASTEXITCODE -ne 0) { Write-Host "(WhatsApp plugin not installed; it may already be, or the network failed: run setup again)" -ForegroundColor Yellow }
  # tutor-replies answers your WhatsApp messages from the tutor (status, move, skip, quiz). It is in this repo: read it first.
  & docker @cli plugins install --link /home/node/plugins/tutor-replies --force --accept-capabilities
  if ($LASTEXITCODE -eq 0) { & docker @cli plugins enable tutor-replies }
  if ($LASTEXITCODE -ne 0) { Write-Host "tutor-replies was not set up: WhatsApp replies won't work, reminders still will. Run setup again to retry." -ForegroundColor Yellow }
  docker compose --profile whatsapp restart openclaw-gateway; Check "restart OpenClaw"
  Wait-Gateway
  & docker @cli config validate
  Write-Host "A QR code appears below. On your phone: WhatsApp > Settings > Linked devices > Link a device." -ForegroundColor Green
  & docker @cli channels login --channel whatsapp
} else { Step "5/6 WhatsApp: skipped (not enabled)" }

Step "6/6 Self-test"
docker compose exec api python3 -m tutor selftest --send

$m = Select-String -Path .env -Pattern '^TUTOR_PORT=(.*)$'
$port = if ($m) { $m.Matches[0].Groups[1].Value } else { "8080" }
Write-Host "`nDone. Open http://127.0.0.1:$port  (admin: http://127.0.0.1:$port/admin)" -ForegroundColor Green
Write-Host "Access token: saved as TUTOR_TOKEN in .env (not printed; open .env to copy it when you sign in)"
if ($enabled -contains "tailscale") {
  $ts = (Select-String -Path .env -Pattern '^TS_HOSTNAME=(.*)$').Matches[0].Groups[1].Value
  Write-Host "Phone: https://$ts.<your-tailnet>.ts.net"
}
Start-Process "http://127.0.0.1:$port"
