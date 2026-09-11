#!/usr/bin/env bash
# Stable public address with Tailscale Funnel (free, HTTPS, fixed hostname, reconnects on its own).
# One-time: install the Tailscale app (brew install --cask tailscale-app), open it and log in; when this script
# prints an "enable Funnel" link, open it once in the browser. After that: sandbox/funnel.sh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TS=/Applications/Tailscale.app/Contents/MacOS/Tailscale
[ -x "$TS" ] || TS="$(command -v tailscale)"
[ -x "$TS" ] || { echo "Tailscale is not installed: brew install --cask tailscale-app, then open it and log in."; exit 1; }
if ! "$TS" status >/dev/null 2>&1; then
  echo "Tailscale is installed but not logged in. Open the Tailscale app from the menu bar and sign in, then run this again."; exit 1
fi
HOST="$("$TS" status --json | python3 -c 'import sys,json; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
# Funnel listens on 443 and forwards to the local backend
"$TS" funnel --bg --https=443 http://127.0.0.1:8000 2>&1 | tail -5
"$TS" funnel status 2>/dev/null | head -5
# stop the Cloudflare quick tunnel machinery so the address stays put
pgrep -f "tunnel_superviso[r]|tunnel_watchdo[g]" | xargs kill 2>/dev/null; pgrep -f "cloudflared tunne[l]" | xargs kill 2>/dev/null
"$ROOT/sandbox/set_public_url.sh" "https://$HOST"
