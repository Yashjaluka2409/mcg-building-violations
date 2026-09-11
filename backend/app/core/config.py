"""
Settings of the Building Violation Management System server (FastAPI + Pydantic v2 settings).

Every value is read from the environment / a `.env` file in the backend folder (see `.env.example`). The
names follow the MCG platform backend (SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, DATABASE_URL,
AWS_S3_BUCKET_NAME ...); the previous edition's names (DJANGO_SECRET_KEY, MEDIA_ROOT) are still accepted.

INTEGRATION NOTE FOR THE MCG IT TEAM: the module is a self-contained FastAPI router mounted at
`/building-violations/`. Inside the platform backend, include `app.routers.building_violations.router`,
register `app.models.building_violations` on the shared metadata and point DATABASE_URL / S3 / SMS at the
platform's own values; nothing else changes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]          # backend/
APP_DIR = BASE_DIR / "app"

# macOS (Homebrew): let WeasyPrint find Pango/Cairo. Linux servers do not need this.
if sys.platform == "darwin":
    for _p in ("/opt/homebrew/lib", "/usr/local/lib"):
        if os.path.isdir(_p):
            os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", _p)
            os.environ.setdefault("WEASYPRINT_DLL_DIRECTORIES", _p)
            break


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore", case_sensitive=False, populate_by_name=True)

    # ---- server / auth (platform names) ------------------------------------------------
    SECRET_KEY: str = Field(default="dev-only-insecure-key-change-me", validation_alias=AliasChoices("SECRET_KEY", "DJANGO_SECRET_KEY"))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 30 * 24 * 60
    DEBUG: bool = Field(default=True, validation_alias=AliasChoices("DEBUG", "DJANGO_DEBUG"))
    DEMO_MODE: bool = False                   # fixed OTP, demo PID records, uploads served by the app
    SERVE_SPA: bool = False                   # serve web/dist from this app on /building-violations/
    SPA_DIST: Path = BASE_DIR.parent / "web" / "dist"
    CORS_ALLOWED_ORIGINS: str = ""
    SCHEDULER: bool = Field(default=True, validation_alias=AliasChoices("BVMS_SCHEDULER", "SCHEDULER"))   # in-process timers (SLA sweep, deadlines, SMS retry)
    TIME_ZONE: str = "Asia/Kolkata"

    # ---- database (PostgreSQL 14+/PostGIS in production, SQLite for the demo) ------------
    DATABASE_URL: str = ""                    # empty = SQLite demo database
    DB_POOL_SIZE: int = 25
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800

    # ---- file storage: AWS S3 (ap-south-1) with automatic fallback to local /uploads ------
    AWS_S3_BUCKET_NAME: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    AWS_S3_PUBLIC_BASE: str = ""              # optional CDN / custom domain in front of the bucket
    UPLOADS_DIR: Path = Field(default=BASE_DIR / "uploads", validation_alias=AliasChoices("UPLOADS_DIR", "MEDIA_ROOT"))
    UPLOADS_URL: str = "/uploads/"

    # ---- module ------------------------------------------------------------------------
    BVMS_USE_PLATFORM_AUTH: bool = False
    PID_API_BASE: str = "https://property.ulbharyana.gov.in/api"
    PID_API_USER: str = ""
    PID_API_PASSWORD: str = ""
    PID_MC_CODE: str = "012"
    PID_PLATFORM_PROXY_URL: str = ""
    PID_TIMEOUT: int = 15
    # SMS: console | http | pixabits (DLT-registered, sender MCGGGN, as on the platform)
    SMS_GATEWAY: str = "console"
    SMS_HTTP_URL: str = ""
    SMS_HTTP_METHOD: str = "POST"
    SMS_HTTP_AUTH_HEADER: str = ""
    SMS_SENDER_ID: str = "MCGGGN"
    SMS_DLT_TEMPLATE_SCN: str = ""
    SMS_DLT_TEMPLATE_ORDER: str = ""
    PIXABITS_API_URL: str = ""
    PIXABITS_API_KEY: str = ""
    PIXABITS_ROUTE: str = "4"
    # WhatsApp alerts through Aisensy (optional)
    AISENSY_API_URL: str = "https://backend.aisensy.com/campaign/t1/api/v2"
    AISENSY_API_KEY: str = ""
    AISENSY_CAMPAIGN_SCN: str = ""
    AISENSY_CAMPAIGN_ORDER: str = ""
    # Digital signature
    SIGNER: str = "local"
    SIGNER_P12_PATH: str = str(APP_DIR / "keys" / "dev-signer.p12")
    SIGNER_P12_PASSWORD: str = "mcgdev"
    SIGNER_PKCS11_LIB: str = ""
    SIGNER_PKCS11_SLOT: str = ""
    SIGNER_ESIGN_URL: str = ""
    SIGNER_ESIGN_ASP_ID: str = ""
    SIGNER_TSA_URL: str = ""
    PUBLIC_VERIFY_BASE: str = "http://localhost:5173/building-violations/verify"
    MCG_NAME_EN: str = "Municipal Corporation Gurugram"
    MCG_NAME_HI: str = "नगर निगम गुरुग्राम"
    MCG_ADDRESS: str = "Civil Lines, Gurugram - 122001, Haryana"
    MCG_HELPLINE: str = "0124-2322877"
    CASE_PREFIX: str = "MCG/BV"
    FONTS_DIR: Path = APP_DIR / "fonts"
    LEGAL_DIR: Path = Field(default=BASE_DIR.parent / "shared" / "legal", validation_alias=AliasChoices("BVMS_LEGAL_DIR", "LEGAL_DIR"))
    BVMS_GEOTAG_TOLERANCE_M: int = 150
    BVMS_OTP_DEMO_CODE: str = "123456"
    # --- Location integrity / anti-spoofing (services/location_integrity.py, services/attestation.py) ---
    BVMS_IP_INTEL_URL: str = ""
    BVMS_TRUSTED_PROXY_HOPS: int = 1
    BVMS_PLAY_INTEGRITY_SA_JSON: str = ""
    BVMS_ANDROID_PACKAGE: str = "in.gov.mcg.buildingviolations"
    BVMS_PLAY_INTEGRITY_REQUIRE_PLAY_RECOGNIZED: bool = True
    BVMS_APP_ATTEST_ROOT_CA: str = ""
    BVMS_APPLE_TEAM_ID: str = ""
    BVMS_IOS_BUNDLE_ID: str = "in.gov.mcg.buildingviolations"
    BVMS_APP_ATTEST_ENV: str = "production"

    # ---- derived helpers -----------------------------------------------------------------
    @property
    def sqlalchemy_url(self) -> str:
        url = (self.DATABASE_URL or "").strip()
        if not url:
            return f"sqlite:///{BASE_DIR / 'bvms.sqlite3'}"
        return url

    @property
    def s3_enabled(self) -> bool:
        return bool(self.AWS_S3_BUCKET_NAME)

    @property
    def pid_api(self) -> dict:
        return {"BASE": self.PID_API_BASE, "USER": self.PID_API_USER, "PASSWORD": self.PID_API_PASSWORD, "MC_CODE": self.PID_MC_CODE,
                "PLATFORM_PROXY_URL": self.PID_PLATFORM_PROXY_URL, "TIMEOUT": self.PID_TIMEOUT}

    @property
    def sms(self) -> dict:
        return {"GATEWAY": self.SMS_GATEWAY, "HTTP_URL": self.SMS_HTTP_URL, "HTTP_METHOD": self.SMS_HTTP_METHOD, "HTTP_AUTH_HEADER": self.SMS_HTTP_AUTH_HEADER,
                "SENDER_ID": self.SMS_SENDER_ID, "DLT_TEMPLATE_SCN": self.SMS_DLT_TEMPLATE_SCN, "DLT_TEMPLATE_ORDER": self.SMS_DLT_TEMPLATE_ORDER,
                "PIXABITS_API_URL": self.PIXABITS_API_URL, "PIXABITS_API_KEY": self.PIXABITS_API_KEY, "PIXABITS_ROUTE": self.PIXABITS_ROUTE}

    @property
    def signer(self) -> dict:
        return {"BACKEND": self.SIGNER, "P12_PATH": self.SIGNER_P12_PATH, "P12_PASSWORD": self.SIGNER_P12_PASSWORD, "PKCS11_LIB": self.SIGNER_PKCS11_LIB,
                "PKCS11_SLOT": self.SIGNER_PKCS11_SLOT, "ESIGN_URL": self.SIGNER_ESIGN_URL, "ESIGN_ASP_ID": self.SIGNER_ESIGN_ASP_ID, "TSA_URL": self.SIGNER_TSA_URL}

    @property
    def corporation(self) -> dict:
        return {"NAME_EN": self.MCG_NAME_EN, "NAME_HI": self.MCG_NAME_HI, "ADDRESS": self.MCG_ADDRESS, "HELPLINE": self.MCG_HELPLINE, "CASE_PREFIX": self.CASE_PREFIX}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
