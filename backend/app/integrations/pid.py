"""
Property-ID (PID) lookup against the DULB Haryana property portal.

The MCG platform already calls  https://property.ulbharyana.gov.in/api/property/...
with HTTP Basic credentials (mcCode=012 for Gurugram). This adapter re-uses the same API.
Two modes:
  * direct   - call the DULB API with credentials from settings (PID_API_USER / PID_API_PASSWORD)
  * proxy    - call the platform's own endpoint (e.g. sms-be /challan/property-details/{pid})
               so credentials stay in one place (PID_PLATFORM_PROXY_URL)
SECURITY NOTE: credentials are read from settings/environment and are never sent to clients.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests

from app.core.config import settings

log = logging.getLogger(__name__)


@dataclass
class PropertyRecord:
    pid: str
    owner_name: str = ""
    mobile: str = ""
    address: str = ""
    ward_no: str = ""
    zone: str = ""
    colony: str = ""
    sector: str = ""
    property_type: str = ""
    sub_type: str = ""
    plot_area_sqyd: str = ""
    covered_area_sqm: str = ""
    floors: str = ""
    latitude: float | None = None
    longitude: float | None = None
    images: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def as_dict(self):
        return self.__dict__.copy()


class PIDClient:
    def __init__(self):
        cfg = settings.pid_api
        self.base = cfg["BASE"].rstrip("/")
        self.auth = (cfg["USER"], cfg["PASSWORD"]) if cfg.get("USER") else None
        self.mc_code = cfg.get("MC_CODE", "012")
        self.proxy = cfg.get("PLATFORM_PROXY_URL", "")
        self.timeout = cfg.get("TIMEOUT", 15)

    # ---- public API -------------------------------------------------------------
    def lookup(self, pid: str) -> PropertyRecord | None:
        pid = pid.strip()
        if not pid:
            return None
        if self.proxy:
            return self._via_proxy(pid)
        if not self.auth:
            log.warning("PID API credentials not configured; returning None for %s", pid)
            return None
        return self._direct_by_pid(pid)

    def nearby(self, lat: float, lng: float, buffer: int = 1, page_size: int = 10) -> list[PropertyRecord]:
        if not self.auth:
            return []
        url = f"{self.base}/property/GetNearByPropertiesByUlB"
        params = {"Lat": lat, "Long": lng, "mcCode": self.mc_code, "defaultbuffer": buffer, "PageNo": 1, "PageSize": page_size}
        try:
            r = requests.get(url, params=params, auth=self.auth, timeout=self.timeout)
            r.raise_for_status()
            data = r.json().get("data") or []
            return [self._normalise(d) for d in data]
        except Exception as exc:  # pragma: no cover - network
            log.error("PID nearby failed: %s", exc)
            return []

    # ---- internals --------------------------------------------------------------
    def _direct_by_pid(self, pid: str) -> PropertyRecord | None:
        # The DULB portal exposes property search by PID; the exact path used by the platform's
        # backend should be confirmed by the IT team (candidates below are tried in order).
        candidates = [
            (f"{self.base}/property/GetPropertyByPID", {"PID": pid, "mcCode": self.mc_code}),
            (f"{self.base}/property/GetPropertyDetails", {"pid": pid, "mcCode": self.mc_code}),
        ]
        for url, params in candidates:
            try:
                r = requests.get(url, params=params, auth=self.auth, timeout=self.timeout)
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                payload = r.json()
                data = payload.get("data") if isinstance(payload, dict) else payload
                if isinstance(data, list):
                    data = data[0] if data else None
                if data:
                    return self._normalise(data)
            except Exception as exc:  # pragma: no cover - network
                log.error("PID lookup via %s failed: %s", url, exc)
        return None

    def _via_proxy(self, pid: str) -> PropertyRecord | None:
        try:
            r = requests.get(self.proxy.format(pid=pid), timeout=self.timeout)
            r.raise_for_status()
            payload = r.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else payload
            return self._normalise(data) if data else None
        except Exception as exc:  # pragma: no cover - network
            log.error("PID proxy lookup failed: %s", exc)
            return None

    @staticmethod
    def _normalise(d: dict) -> PropertyRecord:
        def g(*keys, default=""):
            for k in keys:
                if k in d and d[k] not in (None, ""):
                    return d[k]
            return default
        lat = g("Latitude", "latitude", "Lat", default=None)
        lng = g("Longitude", "longitude", "Long", default=None)
        return PropertyRecord(
            pid=str(g("PID", "pid", "property_id")),
            owner_name=str(g("OwnerName", "owner_name", "Owner")),
            mobile=str(g("MobileNo", "mobile", "Mobile", "MobileNumber")),
            address=str(g("Address", "address", "PropertyAddress")),
            ward_no=str(g("WardNo", "ward_no", "Ward")),
            zone=str(g("Zone", "zone")),
            colony=str(g("Colony", "colony", "ColonyName")),
            sector=str(g("Sector", "sector")),
            property_type=str(g("PropertyType", "property_type")),
            sub_type=str(g("SubType", "sub_type", "PropertySubType")),
            plot_area_sqyd=str(g("PlotArea", "plot_area", "Area")),
            covered_area_sqm=str(g("CoveredArea", "covered_area")),
            floors=str(g("Floors", "NoOfFloors", "floors")),
            latitude=float(lat) if lat not in (None, "") else None,
            longitude=float(lng) if lng not in (None, "") else None,
            images=list(g("ImageUrls", "images", default=[]) or []),
            raw=d,
        )


class DemoPIDClient(PIDClient):
    """Returns deterministic records for demo / tests when no credentials are configured."""
    DEMO = {
        "GGN012345": PropertyRecord(pid="GGN012345", owner_name="Ramesh Kumar", mobile="9811100001", address="H.No. 123, Sector 14, Gurugram", ward_no="19", zone="2", colony="Sector 14", property_type="Residential", plot_area_sqyd="300", floors="S+3", latitude=28.4700, longitude=77.0450),
        "GGN098765": PropertyRecord(pid="GGN098765", owner_name="Sunita Devi", mobile="9811100002", address="Plot 45, Sushant Lok Phase-1, Gurugram", ward_no="30", zone="3", colony="Sushant Lok-1", property_type="Commercial", plot_area_sqyd="500", floors="B+G+4", latitude=28.4620, longitude=77.0800),
    }

    def lookup(self, pid: str):
        return self.DEMO.get(pid.strip().upper())

    def nearby(self, lat, lng, buffer=1, page_size=10):
        return list(self.DEMO.values())


def get_pid_client() -> PIDClient:
    cfg = settings.pid_api
    if cfg.get("USER") or cfg.get("PLATFORM_PROXY_URL"):
        return PIDClient()
    return DemoPIDClient()
