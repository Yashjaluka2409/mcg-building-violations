#!/usr/bin/env bash
# (Re)start the BVMS API server for the sandbox: gunicorn with uvicorn workers on PORT (default 8000),
# the same server arrangement as the MCG platform backend. Safe to run again after backend/.env changes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8000}"
cd "$ROOT/backend"
pgrep -f "gunicorn.*app.main:ap[p]" | xargs kill 2>/dev/null || true
pgrep -f "gunicorn config.wsg[i]" | xargs kill 2>/dev/null || true
sleep 1
FORWARDED_ALLOW_IPS='*' nohup .venv/bin/gunicorn -k uvicorn.workers.UvicornWorker app.main:app -b 127.0.0.1:"$PORT" -w 3 --timeout 180 \
  --access-logfile "$ROOT/sandbox/access.log" --error-logfile "$ROOT/sandbox/error.log" </dev/null >/dev/null 2>&1 &
for i in $(seq 1 30); do
  curl -fs "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && { echo "backend up on http://127.0.0.1:$PORT"; exit 0; }
  sleep 1
done
echo "backend did not come up; see sandbox/error.log"; exit 1
