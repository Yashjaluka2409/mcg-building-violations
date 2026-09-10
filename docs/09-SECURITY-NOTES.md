# 09 - Security notes

1. **PID API credentials are exposed in the current MCG portal bundle.** The production JavaScript at
   `mcg-sms.austere.biz/assets/index-*.js` contains the HTTP Basic username/password used for
   `property.ulbharyana.gov.in`. Anyone can read them. This module keeps PID calls server-side
   (`integrations/pid.py`); the platform team should move their own calls behind the backend and
   rotate the credential with DULB.
2. **Evidence integrity.** SHA-256 per file, distance-from-case check, hash-chained `CaseEvent`
   ledger (`verify_chain`), PAdES-signed PDFs with document hash in the QR. Evidence cannot be deleted
   after submission; edits are events.
3. **Access control.** Every workflow action re-checks role and status server-side
   (`_require_role`, `_require_status`); jurisdiction scoping in `ViolationCaseViewSet.get_queryset`.
4. **Personal data (DPDP Act, 2023).** Notices carry only the data required by law; the public
   verification page exposes notice number, property, addressee name and status - no mobile numbers.
   Media are served behind auth via the API; if `/media/` is public on the platform, add
   X-Accel-Redirect protection for `bvms/`.
5. **OTP.** Standalone mode hashes OTPs, limits attempts (5) and validity (10 min); DEBUG uses a fixed
   demo code - never enable DEBUG in production.
6. **Signing keys.** `building_violations/keys/*.p12` is git-ignored; use the platform's secret store.
7. **Uploads.** File types are whitelisted (images, video, PDF, DOC/XLS); size limit 200 MB; consider
   AV scanning at the reverse proxy.
