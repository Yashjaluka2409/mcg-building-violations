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

Mobile app against the sandbox: `cd mobile && EXPO_PUBLIC_API_BASE=https://<host>/building-violations/api npx expo start`
and open the QR code in Expo Go (same Wi-Fi), or build with EAS using the `uat` profile.
