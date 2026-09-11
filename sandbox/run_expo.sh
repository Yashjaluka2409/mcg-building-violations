#!/usr/bin/env bash
# Starts the Expo dev server for the mobile app against the current sandbox tunnel URL, waits for the
# Expo tunnel, then refreshes sandbox/LINKS.txt and the QR codes (qr-expo-go.png = internet tunnel,
# qr-expo-lan.png = same-Wi-Fi). Usage: nohup sandbox/run_expo.sh [--ios] </dev/null >/dev/null 2>&1 &
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Optional: sandbox/expo_token.env with EXPO_TOKEN=<personal access token from expo.dev> runs Expo under that account.
[ -f "$ROOT/sandbox/expo_token.env" ] && set -a && . "$ROOT/sandbox/expo_token.env" && set +a
PUBLIC_URL="$(cat "$ROOT/sandbox/PUBLIC_URL" 2>/dev/null)"
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)"
cd "$ROOT/mobile"
pgrep -f "expo start --tunne[l]" | xargs kill 2>/dev/null; sleep 1
: > "$ROOT/sandbox/expo.log"
EXPO_PUBLIC_API_BASE="$PUBLIC_URL/building-violations/api" EXPO_NO_TELEMETRY=1 DEBUG=expo:start:server:developmentSession \
  nohup npx expo start --tunnel --port 8081 "$@" < /dev/null >> "$ROOT/sandbox/expo.log" 2>&1 &
for i in $(seq 1 90); do grep -q "Tunnel ready" "$ROOT/sandbox/expo.log" && break; sleep 1; done
sleep 3
HOST="$(curl -s -m 15 -H 'expo-platform: ios' http://127.0.0.1:8081/ | python3 -c 'import sys,json; print(json.load(sys.stdin)["launchAsset"]["url"].split("/")[2])' 2>/dev/null)"
[ -n "$HOST" ] || { echo "Expo tunnel did not come up; see sandbox/expo.log"; exit 1; }
TUNNEL="exp://$HOST"; LAN="exp://$LAN_IP:8081"
"$ROOT/backend/.venv/bin/python" - "$TUNNEL" "$LAN" <<'PY'
import sys, qrcode
qrcode.make(sys.argv[1]).save("../sandbox/qr-expo-go.png")
qrcode.make(sys.argv[2]).save("../sandbox/qr-expo-lan.png")
PY
sed -i '' "s|^Mobile app in Expo Go.*|Mobile app in Expo Go (internet): $TUNNEL   ·   same Wi-Fi as the Mac: $LAN|" "$ROOT/sandbox/LINKS.txt"
echo "$(date '+%F %T') expo up: $TUNNEL | $LAN | api $PUBLIC_URL" >> "$ROOT/sandbox/supervisor.log"
echo "Expo Go (internet): $TUNNEL"; echo "Expo Go (same Wi-Fi): $LAN"
