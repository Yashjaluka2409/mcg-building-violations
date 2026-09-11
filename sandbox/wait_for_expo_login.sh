#!/usr/bin/env bash
# Waits (up to 2 h) for `npx expo login` to be completed on this Mac, then restarts Expo via run_expo.sh so the
# dev server runs under that account (Expo Go signed in to the same account then lists it automatically).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Optional: sandbox/expo_token.env with EXPO_TOKEN=<personal access token from expo.dev> runs Expo under that account.
[ -f "$ROOT/sandbox/expo_token.env" ] && set -a && . "$ROOT/sandbox/expo_token.env" && set +a; cd "$ROOT/mobile"
for i in $(seq 1 480); do
  [ -f "$ROOT/sandbox/expo_token.env" ] && set -a && . "$ROOT/sandbox/expo_token.env" && set +a
  U="$(npx expo whoami 2>/dev/null | tail -1)"
  if [ -n "$U" ] && ! echo "$U" | grep -qi "not logged"; then
    echo "$(date '+%F %T') expo CLI logged in as $U; restarting Expo" >> "$ROOT/sandbox/supervisor.log"
    "$ROOT/sandbox/run_expo.sh" >> "$ROOT/sandbox/supervisor.log" 2>&1; exit 0
  fi
  sleep 15
done
