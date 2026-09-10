#!/usr/bin/env bash
# One-command sandbox: builds the portal, prepares the database with demo data and serves everything
# from one origin (Django + gunicorn on PORT, default 8000). Optionally opens a public Cloudflare
# quick tunnel (no account needed) so the link can be shared for a demo.
#
#   ./sandbox/run_sandbox.sh            # local only  -> http://127.0.0.1:8000/building-violations/
#   ./sandbox/run_sandbox.sh --tunnel   # + public https://<random>.trycloudflare.com link
#
# Requirements: python3 (3.12+), node 20+, pango (for Hindi PDFs), cloudflared (for --tunnel).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8000}"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
grep -q "^DEMO_MODE=" .env || printf "\nDEMO_MODE=1\nSERVE_SPA=1\nDJANGO_DEBUG=0\nDJANGO_ALLOWED_HOSTS=*\n" >> .env
cd "$ROOT/web" && npm install --no-audit --no-fund --loglevel=error && VITE_BASE_PATH=/building-violations/ npm run build
cd "$ROOT/backend"
python manage.py migrate -v 0
if [ ! -f .seeded ]; then python manage.py seed_demo --with-cases && touch .seeded; fi
pkill -f "gunicorn config.wsgi" 2>/dev/null || true
nohup .venv/bin/gunicorn config.wsgi:application -b 127.0.0.1:"$PORT" -w 3 --timeout 180 --access-logfile "$ROOT/sandbox/access.log" --error-logfile "$ROOT/sandbox/error.log" >/dev/null 2>&1 &
echo "Portal:  http://127.0.0.1:$PORT/building-violations/"
if [ "${1:-}" = "--tunnel" ]; then
  command -v cloudflared >/dev/null || { echo "install cloudflared first: brew install cloudflared"; exit 1; }
  pkill -f "cloudflared tunnel" 2>/dev/null || true
  nohup cloudflared tunnel --url "http://127.0.0.1:$PORT" > "$ROOT/sandbox/tunnel.log" 2>&1 &
  for i in $(seq 1 30); do URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$ROOT/sandbox/tunnel.log" | head -1 || true); [ -n "$URL" ] && break; sleep 1; done
  if [ -n "${URL:-}" ]; then
    sed -i '' "s|^PUBLIC_VERIFY_BASE=.*|PUBLIC_VERIFY_BASE=$URL/building-violations/verify|" .env 2>/dev/null || sed -i "s|^PUBLIC_VERIFY_BASE=.*|PUBLIC_VERIFY_BASE=$URL/building-violations/verify|" .env
    pkill -f "gunicorn config.wsgi" 2>/dev/null || true
    nohup .venv/bin/gunicorn config.wsgi:application -b 127.0.0.1:"$PORT" -w 3 --timeout 180 --access-logfile "$ROOT/sandbox/access.log" --error-logfile "$ROOT/sandbox/error.log" >/dev/null 2>&1 &
    echo "Public:  $URL/building-violations/"
    echo "$URL" > "$ROOT/sandbox/PUBLIC_URL"
  else
    echo "Tunnel did not come up; see sandbox/tunnel.log"
  fi
fi
echo "Demo OTP: 123456   Logins: JE 9000000001  AE 9000000002  JC 9000000003  Clerk 9000000004  Admin 9000000009  Planning 9000000011  Revenue 9000000012  Legal 9000000013  GIS lab 9000000014"
