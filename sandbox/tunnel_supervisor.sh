#!/usr/bin/env bash
# Keeps a Cloudflare quick tunnel alive. Quick tunnels die when the connection is lost, so this loop
# starts a new one, writes the fresh URL to sandbox/PUBLIC_URL, updates PUBLIC_VERIFY_BASE in backend/.env
# and restarts the API server so new notices carry the right QR URL. Run with nohup.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
while true; do
  : > "$ROOT/sandbox/tunnel.log"
  cloudflared tunnel --url http://127.0.0.1:8000 --edge-ip-version 4 --protocol http2 >> "$ROOT/sandbox/tunnel.log" 2>&1 &
  CF=$!
  for i in $(seq 1 60); do
    URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$ROOT/sandbox/tunnel.log" | grep -v api.trycloudflare | head -1)
    [ -n "$URL" ] && grep -q "Registered tunnel connection" "$ROOT/sandbox/tunnel.log" && break
    sleep 1
  done
  if [ -n "$URL" ]; then
    echo "$URL" > "$ROOT/sandbox/PUBLIC_URL"
    sed -i '' "s|^PUBLIC_VERIFY_BASE=.*|PUBLIC_VERIFY_BASE=$URL/building-violations/verify|" "$ROOT/backend/.env" 2>/dev/null
    "$ROOT/sandbox/start_backend.sh" >/dev/null 2>&1 || true
    echo "$(date '+%F %T') tunnel up: $URL" >> "$ROOT/sandbox/supervisor.log"
  fi
  wait $CF
  echo "$(date '+%F %T') tunnel exited; restarting in 5s" >> "$ROOT/sandbox/supervisor.log"
  sleep 5
done
