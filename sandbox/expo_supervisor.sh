#!/usr/bin/env bash
# Keeps the Expo dev server alive and pointed at the current sandbox tunnel: whenever sandbox/PUBLIC_URL
# changes (Cloudflare quick tunnels get a new URL after every drop) or Expo has died, restart it via
# run_expo.sh. The Expo Go link (exp://...exp.direct) stays the same across restarts. Run with nohup.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAST=""
pgrep -f "expo start --tunne[l]" >/dev/null && LAST="$(cat "$ROOT/sandbox/PUBLIC_URL" 2>/dev/null)"
while true; do
  URL="$(cat "$ROOT/sandbox/PUBLIC_URL" 2>/dev/null)"
  if [ -n "$URL" ] && { [ "$URL" != "$LAST" ] || ! pgrep -f "expo start --tunne[l]" >/dev/null; }; then
    echo "$(date '+%F %T') expo (re)start for $URL" >> "$ROOT/sandbox/supervisor.log"
    "$ROOT/sandbox/run_expo.sh" >> "$ROOT/sandbox/supervisor.log" 2>&1
    LAST="$URL"
  fi
  sleep 30
done
