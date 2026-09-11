#!/usr/bin/env bash
# Alternative stable address with ngrok (free account: one fixed "static domain"). One-time: sign up at
# https://dashboard.ngrok.com, copy the authtoken and claim the free static domain, then create sandbox/ngrok.env:
#   NGROK_AUTHTOKEN=...            NGROK_DOMAIN=your-name.ngrok-free.app
# Note: ngrok's free tier shows a one-click "Visit Site" warning page to browsers on first visit (API calls are fine).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/sandbox/ngrok.env" ] || { echo "Create sandbox/ngrok.env with NGROK_AUTHTOKEN and NGROK_DOMAIN first."; exit 1; }
set -a; . "$ROOT/sandbox/ngrok.env"; set +a
command -v ngrok >/dev/null || { echo "ngrok is not installed: brew install --cask ngrok"; exit 1; }
ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null
pgrep -f "tunnel_superviso[r]|tunnel_watchdo[g]" | xargs kill 2>/dev/null; pgrep -f "cloudflared tunne[l]" | xargs kill 2>/dev/null
pgrep -f "ngrok http" | xargs kill 2>/dev/null
nohup ngrok http --domain="$NGROK_DOMAIN" 8000 --log "$ROOT/sandbox/ngrok.log" < /dev/null > /dev/null 2>&1 &
sleep 4
"$ROOT/sandbox/set_public_url.sh" "https://$NGROK_DOMAIN"
