"""
Standalone settings for running the Building Violation Management System (BVMS) on its own.

INTEGRATION NOTE FOR THE MCG IT TEAM
------------------------------------
The module is a normal Django app (`building_violations`). To mount it inside the existing
platform (the `sms-be` project) you only need to:
  1. copy `building_violations/` into the project and add it to INSTALLED_APPS,
  2. `path("building-violations/", include("building_violations.urls"))` in the root urls,
  3. set BVMS_USE_PLATFORM_AUTH=1 so the module uses the platform's user model / JWT,
  4. copy the BVMS_* settings block below,
  5. run migrations and `manage.py load_legal_catalogue`.
Everything below that is not prefixed BVMS_ is ordinary project plumbing you already have.
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# macOS (Homebrew) : let WeasyPrint find Pango/Cairo. Linux servers do not need this.
if sys.platform == "darwin":
    for _p in ("/opt/homebrew/lib", "/usr/local/lib"):
        if os.path.isdir(_p):
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = _p + ":" + os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
            os.environ["WEASYPRINT_DLL_DIRECTORIES"] = _p
            break

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
# DEMO_MODE: fixed OTP, demo PID records, media served by Django, SPA served from web/dist - for sandboxes only
BVMS_DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,*").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "https://*.trycloudflare.com,https://*.ts.net,https://*.ngrok-free.app,https://*.ngrok.app,http://localhost:5173,http://127.0.0.1:8000").split(",") if o]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
# Serve the built web portal (web/dist) from Django on /building-violations/ when SERVE_SPA=1
BVMS_SERVE_SPA = os.getenv("SERVE_SPA", "0") == "1"
BVMS_SPA_DIST = Path(os.getenv("SPA_DIST", str(BASE_DIR.parent / "web" / "dist")))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "building_violations",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

# ---- Database: PostgreSQL in production, SQLite for the demo -------------------------
_db_url = os.getenv("DATABASE_URL", "").strip()
if _db_url:
    from urllib.parse import urlparse
    _u = urlparse(_db_url)
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _u.path.lstrip("/"), "USER": _u.username, "PASSWORD": _u.password,
        "HOST": _u.hostname, "PORT": _u.port or 5432,
        "CONN_MAX_AGE": 60,
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "bvms.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]
LANGUAGE_CODE = "en-in"
LANGUAGES = [("en", "English"), ("hi", "Hindi")]
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 200 * 1024 * 1024  # videos up to 200 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [o for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend", "rest_framework.filters.SearchFilter", "rest_framework.filters.OrderingFilter"),
    "DEFAULT_PAGINATION_CLASS": "building_violations.api.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",) + (("rest_framework.renderers.BrowsableAPIRenderer",) if DEBUG else ()),
    "EXCEPTION_HANDLER": "building_violations.api.exceptions.platform_exception_handler",
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "AUTH_HEADER_TYPES": ("Bearer",),
}
SPECTACULAR_SETTINGS = {
    "TITLE": "MCG Building Violation Management System API",
    "DESCRIPTION": "REST API consumed by the MCG web portal module and the MCG HARYANA mobile app (building-violations module).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---- Celery ---------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "") or None
CELERY_TASK_ALWAYS_EAGER = not bool(CELERY_BROKER_URL)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "bvms-sla-sweep": {"task": "building_violations.tasks.sla_sweep", "schedule": 15 * 60},
    "bvms-deadline-sweep": {"task": "building_violations.tasks.deadline_sweep", "schedule": 60 * 60},
    "bvms-sms-retry": {"task": "building_violations.tasks.retry_failed_dispatches", "schedule": 10 * 60},
}

# ---- BVMS module settings (copy this block into the platform settings) ----------------
BVMS_USE_PLATFORM_AUTH = os.getenv("BVMS_USE_PLATFORM_AUTH", "0") == "1"
BVMS_PID_API = {
    "BASE": os.getenv("PID_API_BASE", "https://property.ulbharyana.gov.in/api"),
    "USER": os.getenv("PID_API_USER", ""),
    "PASSWORD": os.getenv("PID_API_PASSWORD", ""),
    "MC_CODE": os.getenv("PID_MC_CODE", "012"),
    "PLATFORM_PROXY_URL": os.getenv("PID_PLATFORM_PROXY_URL", ""),
    "TIMEOUT": 15,
}
BVMS_SMS = {
    "GATEWAY": os.getenv("SMS_GATEWAY", "console"),
    "HTTP_URL": os.getenv("SMS_HTTP_URL", ""),
    "HTTP_METHOD": os.getenv("SMS_HTTP_METHOD", "POST"),
    "HTTP_AUTH_HEADER": os.getenv("SMS_HTTP_AUTH_HEADER", ""),
    "SENDER_ID": os.getenv("SMS_SENDER_ID", "MCGGGN"),
    "DLT_TEMPLATE_SCN": os.getenv("SMS_DLT_TEMPLATE_SCN", ""),
    "DLT_TEMPLATE_ORDER": os.getenv("SMS_DLT_TEMPLATE_ORDER", ""),
}
BVMS_SIGNER = {
    "BACKEND": os.getenv("SIGNER", "local"),
    "P12_PATH": os.getenv("SIGNER_P12_PATH", str(BASE_DIR / "building_violations" / "keys" / "dev-signer.p12")),
    "P12_PASSWORD": os.getenv("SIGNER_P12_PASSWORD", "mcgdev"),
    "PKCS11_LIB": os.getenv("SIGNER_PKCS11_LIB", ""),
    "PKCS11_SLOT": os.getenv("SIGNER_PKCS11_SLOT", ""),
    "ESIGN_URL": os.getenv("SIGNER_ESIGN_URL", ""),
    "ESIGN_ASP_ID": os.getenv("SIGNER_ESIGN_ASP_ID", ""),
    "TSA_URL": os.getenv("SIGNER_TSA_URL", ""),
}
BVMS_PUBLIC_VERIFY_BASE = os.getenv("PUBLIC_VERIFY_BASE", "http://localhost:5173/building-violations/verify")
BVMS_CORPORATION = {
    "NAME_EN": os.getenv("MCG_NAME_EN", "Municipal Corporation Gurugram"),
    "NAME_HI": os.getenv("MCG_NAME_HI", "नगर निगम गुरुग्राम"),
    "ADDRESS": os.getenv("MCG_ADDRESS", "Civil Lines, Gurugram - 122001, Haryana"),
    "HELPLINE": os.getenv("MCG_HELPLINE", "0124-2322877"),
    "CASE_PREFIX": "MCG/BV",
}
BVMS_FONTS_DIR = BASE_DIR / "building_violations" / "fonts"
BVMS_LEGAL_DIR = BASE_DIR.parent / "shared" / "legal"
# Geo-tag tolerance: a delivery/execution photo must be within this many metres of the case point
BVMS_GEOTAG_TOLERANCE_M = int(os.getenv("BVMS_GEOTAG_TOLERANCE_M", "150"))

# --- Location integrity / anti-spoofing (services/location_integrity.py, services/attestation.py) --------------
BVMS_IP_INTEL_URL = os.getenv("BVMS_IP_INTEL_URL", "")            # e.g. https://ipinfo.io/{ip}?token=... ; empty = IP checks off
BVMS_TRUSTED_PROXY_HOPS = int(os.getenv("BVMS_TRUSTED_PROXY_HOPS", "1"))   # X-Forwarded-For entries added by our own proxies
BVMS_PLAY_INTEGRITY_SA_JSON = os.getenv("BVMS_PLAY_INTEGRITY_SA_JSON", "")  # Google service-account key with the Play Integrity API
BVMS_ANDROID_PACKAGE = os.getenv("BVMS_ANDROID_PACKAGE", "in.gov.mcg.buildingviolations")
BVMS_PLAY_INTEGRITY_REQUIRE_PLAY_RECOGNIZED = os.getenv("BVMS_PLAY_INTEGRITY_REQUIRE_PLAY_RECOGNIZED", "1") == "1"
BVMS_APP_ATTEST_ROOT_CA = os.getenv("BVMS_APP_ATTEST_ROOT_CA", "")    # path to Apple_App_Attestation_Root_CA.pem
BVMS_APPLE_TEAM_ID = os.getenv("BVMS_APPLE_TEAM_ID", "")
BVMS_IOS_BUNDLE_ID = os.getenv("BVMS_IOS_BUNDLE_ID", "in.gov.mcg.buildingviolations")
BVMS_APP_ATTEST_ENV = os.getenv("BVMS_APP_ATTEST_ENV", "production")   # production | development
BVMS_OTP_DEMO_CODE = os.getenv("BVMS_OTP_DEMO_CODE", "123456")  # standalone demo only (used when DEBUG or DEMO_MODE)

LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
