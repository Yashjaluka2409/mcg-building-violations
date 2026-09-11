#!/usr/bin/env bash
# One-command sandbox: builds the portal, prepares the database with demo data and serves everything
# from one origin (FastAPI + gunicorn/uvicorn workers on PORT, default 8000). Optionally opens a public
# Cloudflare quick tunnel (no account needed) so the link can be shared for a demo.
#
#   ./sandbox/run_sandbox.sh            # local only  -> http://127.0.0.1:8000/building-violations/
#   ./sandbox/run_sandbox.sh --tunnel   # + public https://<random>.trycloudflare.com link
#
# Requirements: python3 (3.11+), node 20+, pango (for Hindi PDFs), cloudflared (for --tunnel).
# Stable public addresses: sandbox/funnel.sh (Tailscale) or sandbox/ngrok_tunnel.sh (ngrok) instead of --tunnel.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8000}"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
grep -q "^DEMO_MODE=" .env || printf "\nDEMO_MODE=1\nSERVE_SPA=1\nDEBUG=0\n" >> .env
cd "$ROOT/web" && npm install --no-audit --no-fund --loglevel=error && VITE_BASE_PATH=/building-violations/ npm run build
cd "$ROOT/backend"
.venv/bin/python -m app.cli migrate
if [ ! -f .seeded ]; then .venv/bin/python -m app.cli seed-demo --with-cases && touch .seeded; fi
"$ROOT/sandbox/start_backend.sh"
echo "Portal:  http://127.0.0.1:$PORT/building-violations/"
if [ "${1:-}" = "--tunnel" ]; then
  command -v cloudflared >/dev/null || { echo "install cloudflared first: brew install cloudflared"; exit 1; }
  pgrep -f "cloudflared tunne[l]" | xargs kill 2>/dev/null || true
  nohup "$ROOT/sandbox/tunnel_supervisor.sh" </dev/null >/dev/null 2>&1 &
  for i in $(seq 1 60); do URL=$(cat "$ROOT/sandbox/PUBLIC_URL" 2>/dev/null || true); [ -n "$URL" ] && break; sleep 1; done
  if [ -n "${URL:-}" ]; then echo "Public:  $URL/building-violations/"; else echo "Tunnel did not come up; see sandbox/tunnel.log"; fi
fi
echo "Demo OTP: 123456   Logins: JE 9000000001  AE 9000000002  JC 9000000003  Clerk 9000000004  Admin 9000000009  Planning 9000000011  Revenue 9000000012  Legal 9000000013  GIS lab 9000000014"
