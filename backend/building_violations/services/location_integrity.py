"""Location integrity (anti-GPS-spoofing). See docs/09-SECURITY-NOTES.md, section "Location integrity".

Every device location the server is asked to trust (evidence upload, inspection recorded, planned
inspection started/closed, and the app's home-screen pre-check) passes through ``evaluate()``:

1. **Device signals** reported by the app with the fix: mock provider (FlyGPS / Fake GPS and similar),
   iOS software-simulated location, root / jailbreak, emulator, Android Developer options, VPN / system
   proxy, GPS fix age, accuracy radius, jitter between consecutive fixes, whether the native integrity
   module was available (Expo Go and the web portal cannot run it).
2. **Hardware-backed attestation** (Google Play Integrity / Apple App Attest), verified in ``attestation.py``,
   proving the request comes from the genuine, unmodified app on an untampered device.
3. **Server-side checks that no client can fake**: teleport detection against the officer's previous
   accepted location, HTTP proxy headers and, when an IP-intelligence provider is configured, VPN / proxy /
   hosting flags and IP-vs-GPS distance.

The decision (PASS / FLAGGED / REJECTED) and every signal are stored in ``LocationIntegrityCheck`` so rejected
attempts remain on record as incidents. A REJECTED decision raises ``IntegrityError`` (HTTP 400) and the
calling view records nothing as evidence. Which signals block and which only flag is controlled by the
admin through WorkflowSetting (group "Location integrity").
"""
from __future__ import annotations

import ipaddress
import secrets
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings as dj
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ..models import IntegrityNonce, LocationIntegrityCheck
from . import access, attestation
from .geo import haversine_m
from .workflow import WorkflowError

PASS, FLAGGED, REJECTED = "PASS", "FLAGGED", "REJECTED"

# Human-readable explanation per reason code (shown to the officer and in the register).
TEXT = {
    "MOCK_LOCATION": "the device reported a mock (fake) GPS provider such as FlyGPS or Fake GPS Location",
    "SIMULATED_LOCATION": "the location was simulated by software (computer-tethered location spoofing)",
    "EXTERNAL_GPS_ACCESSORY": "the location came from an external GPS accessory",
    "ROOTED_DEVICE": "the device is rooted / jailbroken",
    "EMULATOR": "the app is running on an emulator / simulator",
    "DEVELOPER_OPTIONS": "Android Developer options are enabled (mock-location apps need them)",
    "VPN_ACTIVE": "a VPN is active on the device",
    "PROXY_CONFIGURED": "a system proxy is configured on the device",
    "IP_VPN_OR_PROXY": "the request came from a VPN / proxy / Tor IP address",
    "IP_HOSTING": "the request came from a data-centre / hosting IP address",
    "HTTP_PROXY_HEADERS": "the request passed through an HTTP proxy",
    "IP_FAR_FROM_GPS": "the IP address geolocates far from the reported GPS position",
    "STALE_FIX": "the GPS fix was too old at the moment of capture",
    "FUTURE_TIMESTAMP": "the device clock is ahead of the server",
    "POOR_ACCURACY": "the GPS accuracy radius is too wide",
    "STATIC_FIX": "consecutive GPS fixes were identical (no natural jitter)",
    "IMPLAUSIBLE_TRAVEL": "the officer's previous location implies an impossible travel speed",
    "NO_NATIVE_INTEGRITY": "this app build cannot run the native anti-spoofing checks (Expo Go / development build)",
    "NATIVE_CHECKS_UNAVAILABLE": "this app build cannot run the native anti-spoofing checks (Expo Go / development build)",
    "WEB_UNVERIFIED": "the location came from a web browser and cannot be verified",
    "WEB_GEOTAG": "geotagged field evidence must be captured with the mobile app, not a browser",
    "ATTESTATION_MISSING": "no device attestation (Play Integrity / App Attest) was supplied",
    "ATTESTATION_FAILED": "device attestation failed (modified app or compromised device)",
    "NO_SIGNALS": "the app did not report its device-integrity signals",
}

ADVICE = ("Evidence captured with a spoofed or untrusted location is not accepted. Disable mock-location apps, "
          "VPN / proxy and Developer options, use the official MCG app on an unmodified phone, and try again.")


class IntegrityError(WorkflowError):
    """Rendered as HTTP 400 by the API. Carries the stored check so callers can reference it."""

    def __init__(self, message, check: LocationIntegrityCheck | None = None, status=400):
        super().__init__(message, status)
        self.check = check


def explain(codes) -> str:
    return "; ".join(TEXT.get(c, c) for c in codes)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _tri(v):
    """Tri-state bool: None when the client could not determine the signal."""
    if v is None or v == "":
        return None
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes")
    return bool(v)


def _dec(v):
    try:
        return None if v is None or v == "" else Decimal(str(round(float(v), 3)))
    except (TypeError, ValueError):
        return None


def _client_ip(request):
    if request is None:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")) or None
    try:
        ipaddress.ip_address(ip)
        return ip
    except (ValueError, TypeError):
        return None


def _is_private(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
        return a.is_private or a.is_loopback or a.is_link_local or a.is_reserved
    except ValueError:
        return True


def _xff_hops(request) -> int:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "") if request else ""
    return len([h for h in xff.split(",") if h.strip()]) if xff else 0


def ip_intelligence(ip: str | None) -> dict:
    """Optional: query an IP-intelligence provider (BVMS_IP_INTEL_URL with ``{ip}``; e.g. ipinfo.io with the
    privacy add-on, ipapi.is, ipqualityscore). Normalises the common answer shapes to
    {privacy: bool, hosting: bool, flags: {...}, lat, lng, country, raw}. Cached one hour per IP."""
    url = getattr(dj, "BVMS_IP_INTEL_URL", "")
    if not url or not ip or _is_private(ip):
        return {}
    key = f"bvms:ipintel:{ip}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        r = requests.get(url.format(ip=ip), timeout=3, headers={"Accept": "application/json"})
        data = r.json() if r.ok else {}
    except Exception:  # provider down: never block on it
        return {}
    if not isinstance(data, dict):
        return {}
    priv = data.get("privacy") or data.get("security") or {}
    if not isinstance(priv, dict):
        priv = {}
    flags = {}
    for k in ("vpn", "proxy", "tor", "relay", "hosting", "datacenter", "bogon", "abuser"):
        v = priv.get(k)
        if v is None:
            v = data.get(f"is_{k}", data.get(k))
        flags[k] = bool(v) if isinstance(v, (bool, int)) else str(v).lower() in ("1", "true", "yes")
    out = {"flags": flags, "privacy": any(flags[k] for k in ("vpn", "proxy", "tor", "relay")),
           "hosting": flags.get("hosting") or flags.get("datacenter"), "country": data.get("country") or (data.get("location") or {}).get("country"),
           "raw": {k: data.get(k) for k in ("ip", "org", "asn", "company", "privacy", "security", "loc", "city", "region", "country") if k in data}}
    loc = data.get("loc")
    lat = lng = None
    if isinstance(loc, str) and "," in loc:
        try:
            lat, lng = (float(x) for x in loc.split(",", 1))
        except ValueError:
            pass
    if lat is None:
        src = data.get("location") if isinstance(data.get("location"), dict) else data
        try:
            lat, lng = float(src.get("latitude")), float(src.get("longitude"))
        except (TypeError, ValueError):
            lat = lng = None
    if lat is not None:
        out["lat"], out["lng"] = lat, lng
    cache.set(key, out, 3600)
    return out


# ---------------------------------------------------------------------------
# nonces for attestation (DB-backed so every gunicorn worker sees them)
# ---------------------------------------------------------------------------
NONCE_TTL = timedelta(minutes=15)


def issue_nonce(user) -> str:
    nonce = secrets.token_urlsafe(32)
    IntegrityNonce.objects.create(nonce=nonce, user=user)
    if secrets.randbelow(50) == 0:  # opportunistic purge
        IntegrityNonce.objects.filter(created_at__lt=timezone.now() - NONCE_TTL * 4).delete()
    return nonce


def consume_nonce(user, nonce: str | None) -> bool:
    if not nonce:
        return False
    row = IntegrityNonce.objects.filter(nonce=nonce, user=user, used_at__isnull=True, created_at__gte=timezone.now() - NONCE_TTL).first()
    if not row:
        return False
    row.used_at = timezone.now()
    row.save(update_fields=["used_at"])
    return True


# ---------------------------------------------------------------------------
# the evaluation
# ---------------------------------------------------------------------------
def normalise_signals(signals) -> dict:
    if not isinstance(signals, dict):
        return {}
    return {str(k): v for k, v in signals.items()}


def evaluate(*, user, request, context: str, latitude, longitude, accuracy_m=None, altitude_m=None, captured_at=None,
             signals=None, case=None, task=None, device_id: str = "", persist: bool = True, enforce: bool = True) -> LocationIntegrityCheck:
    """Evaluate one device location. Returns the stored LocationIntegrityCheck; raises IntegrityError when REJECTED
    (after storing it) unless ``enforce`` is False (pre-checks)."""
    S = access.get_setting
    sig = normalise_signals(signals)
    now = timezone.now()
    chk = LocationIntegrityCheck(
        officer=user if getattr(user, "pk", None) else None, context=context, case=case, task=task,
        latitude=latitude, longitude=longitude, accuracy_m=_dec(accuracy_m), altitude_m=_dec(altitude_m), signals=sig,
        device_id=(device_id or sig.get("device_id") or (request.headers.get("X-Device-Id", "") if request else "") or "")[:120],
    )
    src = str(sig.get("source") or "").lower()
    chk.platform = str(sig.get("platform") or ("web" if src == "web" else ""))[:10].lower()
    chk.source = "web" if (src == "web" or chk.platform == "web") else ("app" if sig else "unknown")
    chk.app_version = str(sig.get("app_version") or "")[:40]
    chk.build_number = str(sig.get("build_number") or "")[:40]
    chk.os_version = str(sig.get("os_version") or "")[:40]
    chk.device_model = str(sig.get("device_model") or "")[:80]
    chk.native_module = bool(_tri(sig.get("native_module")))
    for f in ("is_physical_device", "mock_location", "rooted", "developer_options", "vpn_active", "proxy_configured",
              "simulated_by_software", "produced_by_accessory"):
        setattr(chk, f, _tri(sig.get(f)))
    chk.provider = str(sig.get("provider") or "")[:30]
    chk.speed_mps, chk.heading = _dec(sig.get("speed_mps")), _dec(sig.get("heading"))
    chk.jitter_m, chk.fix_age_s = _dec(sig.get("jitter_m")), _dec(sig.get("fix_age_s"))
    fix_at = sig.get("fix_at")
    chk.fix_at = (parse_datetime(fix_at) if isinstance(fix_at, str) else None) or captured_at or now
    if timezone.is_naive(chk.fix_at):
        chk.fix_at = timezone.make_aware(chk.fix_at)
    chk.client_ip = _client_ip(request)

    block: list[str] = []
    flag: list[str] = []

    def hit(code, cond, setting_key, default=True):
        if cond:
            (block if S(setting_key, default) else flag).append(code)

    if latitude is None or longitude is None:
        block.append("NO_LOCATION")

    # 1. device-reported signals -------------------------------------------------
    if chk.source in ("web", "unknown"):
        if S("block_web_geotags", False):
            block.append("WEB_GEOTAG")
        else:
            flag.append("WEB_UNVERIFIED" if chk.source == "web" else "NO_SIGNALS")
    else:
        if not chk.native_module:
            (block if S("require_native_integrity_module", False) else flag).append(
                "NO_NATIVE_INTEGRITY" if S("require_native_integrity_module", False) else "NATIVE_CHECKS_UNAVAILABLE")
        hit("MOCK_LOCATION", chk.mock_location, "block_mock_location")
        hit("SIMULATED_LOCATION", chk.simulated_by_software, "block_mock_location")
        if chk.produced_by_accessory:
            flag.append("EXTERNAL_GPS_ACCESSORY")
        hit("ROOTED_DEVICE", chk.rooted, "block_rooted_devices")
        hit("EMULATOR", chk.is_physical_device is False, "block_emulators")
        hit("DEVELOPER_OPTIONS", chk.developer_options, "block_developer_options")
        hit("VPN_ACTIVE", chk.vpn_active, "block_vpn_or_proxy")
        hit("PROXY_CONFIGURED", chk.proxy_configured, "block_vpn_or_proxy")
        if chk.fix_age_s is not None and float(chk.fix_age_s) > int(S("max_location_age_s", 120)):
            block.append("STALE_FIX")
        if chk.jitter_m is not None and float(chk.jitter_m) == 0 and float(chk.speed_mps or 0) == 0:
            flag.append("STATIC_FIX")
    if chk.accuracy_m is not None and float(chk.accuracy_m) > int(S("max_location_accuracy_m", 100)):
        flag.append("POOR_ACCURACY")
    if captured_at and captured_at > now + timedelta(minutes=5):
        flag.append("FUTURE_TIMESTAMP")

    # 2. hardware-backed attestation ---------------------------------------------
    att = sig.get("attestation") if isinstance(sig.get("attestation"), dict) else {}
    required = bool(S("require_device_attestation", False))
    if chk.source == "app":
        if att.get("token") or att.get("assertion") or att.get("attestation"):
            status, detail = attestation.verify(att, user=user, consume_nonce=consume_nonce)
            chk.attestation_type = str(att.get("type") or "")[:20]
            chk.attestation_status, chk.attestation_detail = status, detail
            if status != "VALID":
                (block if required else flag).append("ATTESTATION_FAILED")
        elif required:
            block.append("ATTESTATION_MISSING")

    # 3. server-side ---------------------------------------------------------------
    if request is not None:
        trusted = int(getattr(dj, "BVMS_TRUSTED_PROXY_HOPS", 1))
        if request.META.get("HTTP_VIA") or request.META.get("HTTP_PROXY_CONNECTION") or _xff_hops(request) > trusted:
            flag.append("HTTP_PROXY_HEADERS")
    intel = ip_intelligence(chk.client_ip)
    if intel:
        chk.ip_intel = intel
        if intel.get("privacy"):
            (block if S("block_vpn_or_proxy", True) else flag).append("IP_VPN_OR_PROXY")
        elif intel.get("hosting"):
            flag.append("IP_HOSTING")
        if intel.get("lat") is not None and latitude is not None:
            km = haversine_m(float(latitude), float(longitude), intel["lat"], intel["lng"]) / 1000
            chk.ip_distance_km = Decimal(str(round(km, 1)))
            lim = int(S("ip_geo_max_distance_km", 500))
            if lim and km > lim:
                flag.append("IP_FAR_FROM_GPS")
    if latitude is not None and chk.officer_id and chk.source == "app":
        # Teleport detection compares real device fixes only (app -> app); browser positions are already unverified.
        prev = (LocationIntegrityCheck.objects.filter(officer=chk.officer, source="app", decision__in=(PASS, FLAGGED), latitude__isnull=False,
                                                       fix_at__gte=chk.fix_at - timedelta(hours=24), fix_at__lte=chk.fix_at + timedelta(hours=24))
                .order_by("-fix_at").first())
        if prev:
            km = haversine_m(float(latitude), float(longitude), float(prev.latitude), float(prev.longitude)) / 1000
            hours = max(abs((chk.fix_at - prev.fix_at).total_seconds()), 1) / 3600
            speed = km / hours
            chk.previous, chk.travel_distance_km, chk.travel_speed_kmph = prev, Decimal(str(round(km, 2))), Decimal(str(round(min(speed, 999999), 1)))
            if km > 1 and speed > int(S("max_plausible_speed_kmph", 200)):
                block.append("IMPLAUSIBLE_TRAVEL")

    chk.reasons, chk.flags = block, flag
    chk.decision = REJECTED if block else (FLAGGED if flag else PASS)
    if persist:
        chk.save()
    if enforce and chk.decision == REJECTED:
        _alert_supervisor(chk)
        raise IntegrityError(f"Location integrity check failed: {explain(block)}. {ADVICE}", chk)
    return chk


def _alert_supervisor(chk: LocationIntegrityCheck):
    """Best effort: tell the officer's reporting officer that a spoofing attempt was blocked."""
    try:
        from .notify import notify_user
        prof = getattr(chk.officer, "bvms_profile", None)
        sup = getattr(prof, "reports_to", None)
        sup_user = getattr(sup, "user", None) or (sup if getattr(sup, "pk", None) and hasattr(sup, "get_username") else None)
        if sup_user:
            notify_user(sup_user, chk.case, "Location integrity rejection",
                        f"{prof.display_name} ({chk.get_context_display()}): {explain(chk.reasons)}. Device {chk.device_model or chk.platform or 'unknown'}, "
                        f"IP {chk.client_ip or '-'}.", level="WARNING")
    except Exception:
        pass


def summary(chk: LocationIntegrityCheck | None) -> dict | None:
    if not chk:
        return None
    return {"id": chk.id, "at": chk.at, "decision": chk.decision, "reasons": chk.reasons, "flags": chk.flags, "explanation": explain(chk.reasons + chk.flags),
            "platform": chk.platform, "source": chk.source, "native_module": chk.native_module, "attestation_status": chk.attestation_status,
            "device_model": chk.device_model, "app_version": chk.app_version, "accuracy_m": chk.accuracy_m, "travel_speed_kmph": chk.travel_speed_kmph}
