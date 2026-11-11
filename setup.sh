#!/usr/bin/env bash
# Teacher Tool setup (Linux/macOS). Safe to re-run: keeps saved secrets unless you change them.
set -euo pipefail
cd "$(dirname "$0")"
step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
need() { command -v "$1" >/dev/null || { echo "Missing $1. $2"; exit 1; }; }

step "1/6 Checking Docker"
need docker "Install Docker: https://docs.docker.com/engine/install/"
docker info >/dev/null 2>&1 || { echo "Docker is installed but not running. Start it and re-run."; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose v2 is required."; exit 1; }

step "2/6 Building the tutor"
docker compose build api
# The setup wizard runs from its own image; rebuild it too or it keeps running an old copy (cached layers, so this is quick)
docker compose --profile setup build setup

docker ps -aq --filter "name=teacher-tool-wizard-run" | xargs -r docker rm -f >/dev/null
DOCKER_PORTS=" $(docker ps --format '{{.Ports}}' | grep -oE ':[0-9]+->' | tr -d ':->' | sort -u | tr '\n' ' ') "
port_busy() { [[ "$DOCKER_PORTS" == *" $1 "* ]] || (exec 3<>/dev/tcp/127.0.0.1/"$1") 2>/dev/null; }
free_port() { local p=$1; while port_busy "$p"; do p=$((p+1)); done; echo "$p"; }
step "3/6 Setup: answer the questions in this window (Claude login, speech, WhatsApp, checks)"
docker compose --profile setup run --rm setup

PROFILES=()
if [[ -f setup/profiles.txt ]]; then
  while read -r p; do [[ -n "$p" ]] && PROFILES+=(--profile "$p"); done < setup/profiles.txt
fi

step "4/6 Starting services"
if [[ -z "$(docker compose ps -q api 2>/dev/null)" ]] && port_busy 8080 && ! grep -q '^TUTOR_PORT=' .env; then
  TP=$(free_port 8081); echo "Port 8080 is busy; the tutor will use port ${TP}."; echo "TUTOR_PORT=${TP}" >> .env
fi
# OpenClaw runs as uid 1000 and can't use a Windows folder for its files, so its home is a Docker volume that is prepared first
if grep -qx whatsapp setup/profiles.txt 2>/dev/null; then
  docker compose --profile whatsapp --profile whatsapp-cli run --rm openclaw-plugin-sync
fi
docker compose "${PROFILES[@]}" up -d --build

# The one-off OpenClaw commands share the gateway's network, which has no DNS while the gateway is starting or restarting
# (EAI_AGAIN on npm and WhatsApp), so wait until it reports healthy before each of them.
wait_gateway() {
  local id i; id=$(docker compose --profile whatsapp ps -q openclaw-gateway 2>/dev/null)
  [[ -n "$id" ]] || return 0
  for ((i = 0; i < 72; i++)); do
    [[ "$(docker inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null)" == healthy ]] && return 0
    [[ $i -eq 0 ]] && echo "Waiting for the OpenClaw gateway to start (up to 6 minutes)..."
    sleep 5
  done
  echo "(the OpenClaw gateway is not healthy yet; carrying on)"
}

if grep -qx whatsapp setup/profiles.txt 2>/dev/null; then
  step "5/6 WhatsApp: installing the plugin and pairing"
  wait_gateway
  CLI=(docker compose --profile whatsapp --profile whatsapp-cli run --rm openclaw-cli)
  # npm only (no ClawHub); Docker's DNS sometimes drops a lookup, so try a few times
  for i in 1 2 3; do
    "${CLI[@]}" plugins install npm:@openclaw/whatsapp --force && break
    [[ $i -lt 3 ]] && { echo "(attempt $i of 3 failed; trying again in 10 seconds)"; sleep 10; }
  done || echo "(WhatsApp plugin not installed; it may already be, or the network failed: run setup again)"
  # tutor-replies answers your WhatsApp messages from the tutor (status, move, skip, quiz). It is in this repo: read it first.
  "${CLI[@]}" plugins install --link /home/node/plugins/tutor-replies --force --accept-capabilities \
    && "${CLI[@]}" plugins enable tutor-replies \
    || echo "tutor-replies was not set up: WhatsApp replies won't work, reminders still will. Run setup again to retry."
  docker compose --profile whatsapp restart openclaw-gateway
  wait_gateway
  "${CLI[@]}" config validate
  echo "A QR code appears below. On your phone: WhatsApp > Settings > Linked devices > Link a device."
  "${CLI[@]}" channels login --channel whatsapp
else
  step "5/6 WhatsApp: skipped (not enabled)"
fi

step "6/6 Self-test"
docker compose exec api python3 -m tutor selftest --send || true

echo
PORT=$(grep '^TUTOR_PORT=' .env | cut -d= -f2-); PORT=${PORT:-8080}
echo "Done. Open http://127.0.0.1:${PORT} (admin: http://127.0.0.1:${PORT}/admin)"
echo "Access token: saved as TUTOR_TOKEN in .env (not printed; open .env to copy it when you sign in)"
grep -qx tailscale setup/profiles.txt 2>/dev/null && echo "Phone: https://$(grep '^TS_HOSTNAME=' .env | cut -d= -f2-).<your-tailnet>.ts.net"
