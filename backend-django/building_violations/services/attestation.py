"""Hardware-backed device attestation for the mobile app.

Android: Google Play Integrity API (standard request). The app asks Play services for a token bound to the
server nonce (request hash); the server decodes it through ``playintegrity.googleapis.com`` with a service
account and checks the app / device verdicts. Configuration: BVMS_PLAY_INTEGRITY_SA_JSON (service-account key
file, Play Integrity API enabled, app linked in Play Console), BVMS_ANDROID_PACKAGE.

iOS: Apple App Attest (DeviceCheck framework). On first use the app creates a key in the Secure Enclave and
sends the *attestation object*; every later capture sends an *assertion* signed by that key over the server
nonce. The server verifies the certificate chain against Apple's App Attest root CA
(BVMS_APP_ATTEST_ROOT_CA = path to Apple_App_Attestation_Root_CA.pem from apple.com/certificateauthority),
the nonce, the App ID hash (BVMS_APPLE_TEAM_ID.BVMS_IOS_BUNDLE_ID), the AAGUID environment and the
counter, and stores the public key per key id (AppAttestKey).

``verify()`` never raises: it returns (status, detail) with status VALID | INVALID | UNSUPPORTED | ERROR.
Payload shape sent by the app inside ``location_integrity.attestation``::

    {"type": "play_integrity", "token": "...", "nonce": "..."}
    {"type": "app_attest", "key_id": "...", "attestation": "<b64 CBOR>", "nonce": "..."}      # first use
    {"type": "app_attest", "key_id": "...", "assertion": "<b64 CBOR>", "nonce": "..."}        # later
"""
from __future__ import annotations

import base64
import hashlib
import json
import time

import requests
from django.conf import settings as dj
from django.core.cache import cache
from django.utils import timezone

PLAY_SCOPE = "https://www.googleapis.com/auth/playintegrity"
APP_ATTEST_NONCE_OID = "1.2.840.113635.100.8.2"


def verify(att: dict, *, user, consume_nonce) -> tuple[str, dict]:
    kind = str(att.get("type") or "").lower()
    nonce = att.get("nonce")
    try:
        if kind == "play_integrity":
            if not consume_nonce(user, nonce):
                return "INVALID", {"error": "nonce unknown, expired or already used"}
            return verify_play_integrity(att.get("token", ""), nonce)
        if kind == "app_attest":
            if not consume_nonce(user, nonce):
                return "INVALID", {"error": "nonce unknown, expired or already used"}
            if att.get("attestation"):
                return verify_app_attest_attestation(att["key_id"], att["attestation"], nonce, user)
            return verify_app_attest_assertion(att["key_id"], att.get("assertion", ""), nonce, user)
        return "UNSUPPORTED", {"error": f"unknown attestation type {kind!r}"}
    except Exception as e:  # never let attestation parsing crash an upload
        return "ERROR", {"error": f"{type(e).__name__}: {e}"[:300]}


# ---------------------------------------------------------------------------
# Google Play Integrity
# ---------------------------------------------------------------------------
def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _google_access_token(sa_path: str) -> str:
    """OAuth2 JWT-bearer flow with the service-account key (no google-auth dependency)."""
    key = f"bvms:google-token:{sa_path}"
    tok = cache.get(key)
    if tok:
        return tok
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    with open(sa_path, "rb") as fh:
        sa = json.load(fh)
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64url(json.dumps({"iss": sa["client_email"], "scope": PLAY_SCOPE, "aud": sa["token_uri"], "iat": now, "exp": now + 3600}).encode())
    signing_input = f"{header}.{claims}".encode()
    pk = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = pk.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    assertion = f"{header}.{claims}.{_b64url(sig)}"
    r = requests.post(sa["token_uri"], data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}, timeout=10)
    r.raise_for_status()
    tok = r.json()["access_token"]
    cache.set(key, tok, 50 * 60)
    return tok


def verify_play_integrity(token: str, nonce: str) -> tuple[str, dict]:
    sa_path = getattr(dj, "BVMS_PLAY_INTEGRITY_SA_JSON", "")
    package = getattr(dj, "BVMS_ANDROID_PACKAGE", "")
    if not sa_path or not package:
        return "UNSUPPORTED", {"error": "Play Integrity not configured on the server (BVMS_PLAY_INTEGRITY_SA_JSON / BVMS_ANDROID_PACKAGE)"}
    if not token:
        return "INVALID", {"error": "empty token"}
    access_token = _google_access_token(sa_path)
    r = requests.post(f"https://playintegrity.googleapis.com/v1/{package}:decodeIntegrityToken",
                      json={"integrity_token": token}, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if not r.ok:
        return "INVALID", {"error": f"decode failed HTTP {r.status_code}", "body": r.text[:300]}
    payload = r.json().get("tokenPayloadExternal") or {}
    req = payload.get("requestDetails") or {}
    app = payload.get("appIntegrity") or {}
    dev = payload.get("deviceIntegrity") or {}
    acct = payload.get("accountDetails") or {}
    detail = {"request": req, "app": app.get("appRecognitionVerdict"), "device": dev.get("deviceRecognitionVerdict"), "licensing": acct.get("appLicensingVerdict")}
    # the app binds the standard request to sha256(nonce) as requestHash; classic requests carry the nonce itself
    expected_hashes = {nonce, hashlib.sha256(nonce.encode()).hexdigest(), _b64url(hashlib.sha256(nonce.encode()).digest()), base64.b64encode(nonce.encode()).decode()}
    got = req.get("requestHash") or req.get("nonce") or ""
    if got not in expected_hashes:
        return "INVALID", {**detail, "error": "request hash / nonce mismatch"}
    if req.get("requestPackageName") not in (None, package):
        return "INVALID", {**detail, "error": "package name mismatch"}
    ts = int(req.get("timestampMillis") or 0)
    if ts and abs(time.time() * 1000 - ts) > 10 * 60 * 1000:
        return "INVALID", {**detail, "error": "token too old"}
    verdicts = set(dev.get("deviceRecognitionVerdict") or [])
    if not ({"MEETS_DEVICE_INTEGRITY", "MEETS_STRONG_INTEGRITY"} & verdicts):
        return "INVALID", {**detail, "error": "device does not meet integrity"}
    if getattr(dj, "BVMS_PLAY_INTEGRITY_REQUIRE_PLAY_RECOGNIZED", True) and app.get("appRecognitionVerdict") != "PLAY_RECOGNIZED":
        return "INVALID", {**detail, "error": "app not recognised by Play (modified or side-loaded build)"}
    return "VALID", detail


# ---------------------------------------------------------------------------
# Apple App Attest
# ---------------------------------------------------------------------------
def _app_id_hash() -> bytes | None:
    team, bundle = getattr(dj, "BVMS_APPLE_TEAM_ID", ""), getattr(dj, "BVMS_IOS_BUNDLE_ID", "")
    return hashlib.sha256(f"{team}.{bundle}".encode()).digest() if team and bundle else None


def _load_root():
    path = getattr(dj, "BVMS_APP_ATTEST_ROOT_CA", "")
    if not path:
        return None
    from cryptography import x509
    with open(path, "rb") as fh:
        return x509.load_pem_x509_certificate(fh.read())


def _verify_chain(certs, root):
    from cryptography.hazmat.primitives.asymmetric import ec
    now = timezone.now()
    chain = list(certs) + [root]
    for i, cert in enumerate(chain[:-1]):
        issuer = chain[i + 1]
        if cert.issuer != issuer.subject:
            raise ValueError("certificate chain broken")
        issuer.public_key().verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(cert.signature_hash_algorithm))
        if not (cert.not_valid_before_utc <= now <= cert.not_valid_after_utc):
            raise ValueError("certificate expired / not yet valid")


def _parse_auth_data(auth: bytes) -> dict:
    out = {"rp_id_hash": auth[:32], "flags": auth[32], "counter": int.from_bytes(auth[33:37], "big")}
    if len(auth) > 55:
        out["aaguid"] = auth[37:53]
        n = int.from_bytes(auth[53:55], "big")
        out["credential_id"] = auth[55:55 + n]
    return out


def verify_app_attest_attestation(key_id: str, attestation_b64: str, nonce: str, user) -> tuple[str, dict]:
    import cbor2
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from ..models import AppAttestKey
    root, app_hash = _load_root(), _app_id_hash()
    if root is None or app_hash is None:
        return "UNSUPPORTED", {"error": "App Attest not configured on the server (BVMS_APP_ATTEST_ROOT_CA / BVMS_APPLE_TEAM_ID / BVMS_IOS_BUNDLE_ID)"}
    obj = cbor2.loads(base64.b64decode(attestation_b64))
    if obj.get("fmt") != "apple-appattest":
        return "INVALID", {"error": "not an apple-appattest object"}
    certs = [x509.load_der_x509_certificate(c) for c in obj["attStmt"]["x5c"]]
    _verify_chain(certs, root)
    leaf, auth = certs[0], obj["authData"]
    client_hash = hashlib.sha256(nonce.encode()).digest()
    expected_nonce = hashlib.sha256(auth + client_hash).digest()
    ext = leaf.extensions.get_extension_for_oid(x509.ObjectIdentifier(APP_ATTEST_NONCE_OID)).value.value
    if ext[-32:] != expected_nonce:  # ASN.1 SEQUENCE { [1] OCTET STRING nonce } - the nonce is the trailing 32 bytes
        return "INVALID", {"error": "nonce mismatch in attestation certificate"}
    pub = leaf.public_key()
    point = pub.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    kid = base64.b64decode(key_id)
    if hashlib.sha256(point).digest() != kid:
        return "INVALID", {"error": "key id does not match the attested public key"}
    ad = _parse_auth_data(auth)
    if ad["rp_id_hash"] != app_hash:
        return "INVALID", {"error": "App ID mismatch"}
    if ad["counter"] != 0:
        return "INVALID", {"error": "counter must be 0 on attestation"}
    env = getattr(dj, "BVMS_APP_ATTEST_ENV", "production")
    want = b"appattestdevelop" if env == "development" else b"appattest" + b"\x00" * 7
    if ad.get("aaguid") != want:
        return "INVALID", {"error": f"AAGUID is not the {env} environment"}
    if ad.get("credential_id") != kid:
        return "INVALID", {"error": "credential id mismatch"}
    pem = pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    AppAttestKey.objects.update_or_create(key_id=key_id, defaults={"user": user, "public_key_pem": pem, "counter": 0, "environment": env})
    return "VALID", {"key_id": key_id, "environment": env, "first_use": True}


def verify_app_attest_assertion(key_id: str, assertion_b64: str, nonce: str, user) -> tuple[str, dict]:
    import cbor2
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from ..models import AppAttestKey
    app_hash = _app_id_hash()
    if app_hash is None:
        return "UNSUPPORTED", {"error": "App Attest not configured on the server"}
    key = AppAttestKey.objects.filter(key_id=key_id, user=user).first()
    if not key:
        return "INVALID", {"error": "unknown key id for this officer; the app must attest first"}
    obj = cbor2.loads(base64.b64decode(assertion_b64))
    auth, sig = obj["authenticatorData"], obj["signature"]
    client_hash = hashlib.sha256(nonce.encode()).digest()
    digest = hashlib.sha256(auth + client_hash).digest()
    pub = serialization.load_pem_public_key(key.public_key_pem.encode())
    pub.verify(sig, digest, ec.ECDSA(hashes.SHA256()))
    ad = _parse_auth_data(auth)
    if ad["rp_id_hash"] != app_hash:
        return "INVALID", {"error": "App ID mismatch"}
    if ad["counter"] <= key.counter:
        return "INVALID", {"error": "assertion counter did not increase (replay)"}
    key.counter, key.last_used_at = ad["counter"], timezone.now()
    key.save(update_fields=["counter", "last_used_at"])
    return "VALID", {"key_id": key_id, "counter": ad["counter"]}
