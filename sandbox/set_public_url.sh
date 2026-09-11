#!/usr/bin/env bash
# Point the whole sandbox at a public address: writes sandbox/PUBLIC_URL, updates PUBLIC_VERIFY_BASE in
# backend/.env (QR codes on notices), reloads gunicorn, refreshes LINKS.txt and restarts the Expo dev server so
# the app's default server changes too. Usage: sandbox/set_public_url.sh https://host.example
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
URL="${1%/}"
[ -n "$URL" ] || { echo "usage: $0 https://public-host"; exit 1; }
echo "$URL" > "$ROOT/sandbox/PUBLIC_URL"
sed -i '' "s|^PUBLIC_VERIFY_BASE=.*|PUBLIC_VERIFY_BASE=$URL/building-violations/verify|" "$ROOT/backend/.env"
pgrep -f "gunicorn config.wsg[i]" | head -1 | xargs -I{} kill -HUP {} 2>/dev/null
sed -i '' "s|^Web portal (any browser / phone):.*|Web portal (any browser / phone): $URL/building-violations/|" "$ROOT/sandbox/LINKS.txt"
echo "$(date '+%F %T') public url set to $URL" >> "$ROOT/sandbox/supervisor.log"
"$ROOT/sandbox/run_expo.sh" >/dev/null 2>&1 &
echo "Sandbox now public at: $URL/building-violations/"
