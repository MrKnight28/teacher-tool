# Update the Teacher Tool on this PC: get the latest code, rebuild, open the admin page, show what's ready for sttbench.
# Run from the repo folder:  powershell -ExecutionPolicy Bypass -File .\update.ps1
# Add -Bench to also run the speech comparison once you have recorded all 10 sentences.
# Keys and tokens are never printed. Recording the sentences is done in the admin page (it needs the microphone).
param([switch]$Bench)
$ErrorActionPreference = "Continue"  # git and docker write progress to stderr; exit codes are checked instead
Set-Location $PSScriptRoot
function Step($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function Fail($msg) { Write-Host $msg -ForegroundColor Red; exit 1 }

Step "1/4 Getting the latest code"
$all = git status --porcelain --untracked-files=no
# Edits under docs/ (handoff notes, guides) don't block the update. git pull still refuses if it would overwrite them.
$docsOnly = @($all | Where-Object { $_ -match '^.. docs/' })
if ($docsOnly) { Write-Host "Local doc edits kept (git pull will stop if upstream changed the same file):" -ForegroundColor Yellow; $docsOnly | ForEach-Object { Write-Host $_ } }
$changed = @($all | Where-Object { $_ -notmatch '^.. docs/' })
if ($changed) {
  Write-Host "You have local changes to tracked files, so the update is paused. Check them first:" -ForegroundColor Yellow
  git status --short
  exit 1
}
git pull
if ($LASTEXITCODE -ne 0) { Fail "git pull failed. Check your internet connection and run this again." }

Step "2/4 Rebuilding and starting the tutor"
docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail "Docker Desktop is not running. Start it, wait for 'Engine running', then run this again." }
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Fail "docker compose failed. Read the error above." }

$port = "8080"
$envLine = Select-String -Path .env -Pattern '^TUTOR_PORT=(.*)$' -ErrorAction SilentlyContinue
if ($envLine) { $port = $envLine.Matches[0].Groups[1].Value }
$base = "http://127.0.0.1:$port"
$up = $false
for ($i = 0; $i -lt 30 -and -not $up; $i++) {
  try { Invoke-WebRequest -Uri $base -UseBasicParsing -TimeoutSec 3 | Out-Null; $up = $true } catch { Start-Sleep -Seconds 2 }
}
if (-not $up) { Fail "The tutor did not answer at $base after one minute. Run: docker compose logs api" }
Write-Host "The tutor answers at $base" -ForegroundColor Green

Step "3/4 Speech test samples"
$folder = Join-Path $PSScriptRoot "data\stt-samples"
$sentences = @(Get-ChildItem -Path $folder -Filter *.txt -ErrorAction SilentlyContinue)
$recorded = @($sentences | Where-Object { Test-Path (Join-Path $folder ($_.BaseName + ".wav")) })
Write-Host "Recorded: $($recorded.Count) of $($sentences.Count) sentences"
if ($sentences.Count -eq 0) { Write-Host "No sentence files found in data\stt-samples." -ForegroundColor Yellow }
elseif ($recorded.Count -lt $sentences.Count) { Write-Host "Record the rest in the admin page (Voice card, 'Record speech test samples')." -ForegroundColor Yellow }

Step "4/4 Admin page"
Start-Process "$base/admin"
Write-Host "Open: $base/admin  (paste your access token from .env, then press Load)"

if ($Bench) {
  if ($recorded.Count -eq 0) { Fail "No recordings yet, so there is nothing to compare. Record some first." }
  Step "Running the speech comparison (10 to 20 minutes; keep the PC otherwise idle)"
  docker compose exec api python3 -m tutor sttbench
  if ($LASTEXITCODE -ne 0) { Fail "sttbench failed. Read the error above." }
  Write-Host "Results are in the admin Voice card, and in data\sttbench.json." -ForegroundColor Green
}
