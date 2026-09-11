#!/usr/bin/env bash
# Cloudflare quick tunnels sometimes stay alive as a process while the edge has forgotten them
# ("Unauthorized: Tunnel not found" / "Connection terminated" in tunnel.log, nothing served). The supervisor only
# restarts cloudflared when it exits, so this watchdog kills it in that state; the supervisor then brings up a new
# URL, updates PUBLIC_URL / PUBLIC_VERIFY_BASE, restarts the API server, and the Expo supervisor re-points the app.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
while true; do
  L="$ROOT/sandbox/tunnel.log"
  if [ -f "$L" ]; then
    LAST_REG=$(grep -n "Registered tunnel connection" "$L" | tail -1 | cut -d: -f1); LAST_REG=${LAST_REG:-0}
    LAST_BAD=$(grep -n -E "Tunnel not found|Connection terminated|failed to serve incoming request" "$L" | tail -1 | cut -d: -f1); LAST_BAD=${LAST_BAD:-0}
    if [ "$LAST_BAD" -gt "$LAST_REG" ]; then
      sleep 90   # give cloudflared a chance to re-register on its own
      LAST_REG2=$(grep -n "Registered tunnel connection" "$L" | tail -1 | cut -d: -f1); LAST_REG2=${LAST_REG2:-0}
      if [ "$LAST_BAD" -gt "$LAST_REG2" ]; then
        echo "$(date '+%F %T') watchdog: tunnel lost at the edge; restarting cloudflared" >> "$ROOT/sandbox/supervisor.log"
        pgrep -f "cloudflared tunne[l]" | xargs kill 2>/dev/null
        sleep 60
      fi
    fi
  fi
  sleep 60
done
