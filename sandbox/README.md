# Sandbox / demo deployment

| Option | Command | Result |
|---|---|---|
| Demo from a laptop, public link | `./sandbox/run_sandbox.sh --tunnel` | `https://<random>.trycloudflare.com/building-violations/` (lives while the laptop and the script run) |
| Local only | `./sandbox/run_sandbox.sh` | `http://127.0.0.1:8000/building-violations/` |
| IT-team sandbox server (Docker) | `docker compose -f sandbox/docker-compose.yml up -d --build` | `http://<server>:8000/building-violations/` behind the platform's nginx (`sms-sandbox-*.austere.biz`) |

Demo mode (`DEMO_MODE=1`): OTP is always **123456**, PID lookups use two demo records (GGN012345, GGN098765),
SMS goes to the log, notices are signed with a self-signed test certificate. Never enable on production.

Demo logins: JE 9000000001 · AE 9000000002 · JC 9000000003 · JC clerk 9000000004 · XEN 9000000005 ·
Field squad 9000000006 · Additional Commissioner 9000000007 · Admin 9000000009 · Planning branch 9000000011 ·
Revenue branch 9000000012 · Legal branch 9000000013 · GIS lab 9000000014.

Mobile app against the sandbox: `nohup sandbox/expo_supervisor.sh </dev/null >/dev/null 2>&1 &` starts the Expo dev
server (`run_expo.sh`) against the current `PUBLIC_URL`, restarts it whenever that URL changes, and refreshes
`LINKS.txt`, `qr-expo-go.png` (internet, via the Expo tunnel) and `qr-expo-lan.png` (same Wi-Fi as the Mac).
Testers need the current Expo Go from the App Store / Play Store (the project is Expo SDK 57). Open Expo Go,
scan the QR with the phone camera or use "Enter URL manually" and paste the `exp://` link. If the tunnel URL has
changed since the app was loaded, tap "Server … change" on the app's login screen and enter the new portal
address. For a permanent build use EAS with the `uat` profile.

## Keeping the laptop tunnel alive

Cloudflare quick tunnels are deleted by Cloudflare when the connection drops for a few minutes (laptop sleep,
Wi-Fi/VPN change), and the URL then changes. `sandbox/tunnel_supervisor.sh` restarts the tunnel automatically,
writes the current URL to `sandbox/PUBLIC_URL`, updates `PUBLIC_VERIFY_BASE` and reloads gunicorn. Always read
the current link from `sandbox/PUBLIC_URL` (or `sandbox/LINKS.txt`) before sharing it, keep the laptop plugged in
and awake (`caffeinate -dims`), and use the IT team's Docker sandbox for anything that must stay up.
