"""Django settings for the platform backend.

A single settings module driven by environment variables. Each app built on the
platform is its own deployment, configured through these variables.
"""

from datetime import timedelta
from email.utils import formataddr
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from config.env import env_bool, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent

# Read before any dotenv file is loaded: `vercel env pull` writes VERCEL=1 into
# .env.local, and picking that up locally would switch on production behaviour
# (SSL-only database, DEBUG off) on a development machine.
ON_VERCEL = env_bool("VERCEL", False)

# .env is the hand-written local config and wins deliberately: .env.local holds
# remote credentials and must never quietly become the database that local
# development and tests talk to.
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local")

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "" if ON_VERCEL else "insecure-dev-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", not ON_VERCEL)

if ON_VERCEL and not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set on Vercel.")

# --- Identity ---------------------------------------------------------------

# Each deployment is its own white-labelled product built from the same apps.
# Everything that names it to people (emails, the admin, the API docs, the
# frontend via /api/v1/site/) reads this rather than spelling out a name.
SITE_NAME = env_str("SITE_NAME", "ehsundar")

# Vercel gives each deployment its own hostname, so trust them alongside any
# custom domains listed in DJANGO_ALLOWED_HOSTS.
VERCEL_HOSTS = [
    host
    for host in (
        env_str("VERCEL_URL"),
        env_str("VERCEL_BRANCH_URL"),
        env_str("VERCEL_PROJECT_PRODUCTION_URL"),
    )
    if host
]
# On a Vercel Services deployment the frontend reaches this service over
# Vercel's internal network, so the Host header is an opaque per-deployment
# name like `backend.<id>.services.vercel-infra.com` that no env var exposes.
# The leading dot makes Django trust that whole internal domain.
VERCEL_INTERNAL_HOST_SUFFIX = ".services.vercel-infra.com"

ALLOWED_HOSTS = (
    env_list("DJANGO_ALLOWED_HOSTS", ["*"] if DEBUG else [])
    + VERCEL_HOSTS
    + ([VERCEL_INTERNAL_HOST_SUFFIX] if ON_VERCEL else [])
)

# --- Applications ---------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.profiles",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Serves static files under `vercel dev` and `runserver`; on Vercel the CDN
    # serves the collected files and WhiteNoise simply stands down.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
# Vercel picks the ASGI entrypoint whenever ASGI_APPLICATION is also set. This
# is a synchronous app, so it deliberately declares WSGI only.
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Data -----------------------------------------------------------------

# Postgres everywhere, including tests -- `docker compose up -d db` locally.
LOCAL_DATABASE_URL = "postgres://ehsundar:ehsundar@localhost:5434/ehsundar"
DATABASE_URL = env_str("DATABASE_URL", "" if ON_VERCEL else LOCAL_DATABASE_URL)

if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL must be set on Vercel.")

# Serverless invocations are short-lived and Neon pools connections upstream, so
# persistent connections are off on Vercel and on locally.
DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=0 if ON_VERCEL else 600,
        conn_health_checks=not ON_VERCEL,
        ssl_require=ON_VERCEL,
    )
}

# The Neon store is shared with another project, so this platform gets a database
# of its own inside it. Overriding the name here leaves the integration-managed
# DATABASE_URL untouched. (A search_path override is not an option: Neon's pooled
# endpoint rejects `options=-c search_path=...` as a startup parameter.)
DATABASE_NAME = env_str("DATABASE_NAME", "")
if DATABASE_NAME:
    DATABASES["default"]["NAME"] = DATABASE_NAME

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

TEST_RUNNER = "config.test_runner.SafeDiscoverRunner"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalisation -------------------------------------------------

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static and media -----------------------------------------------------

# Vercel runs collectstatic during the build and serves STATIC_ROOT from its CDN.
# Kept under /api/ with everything else, so a single frontend rewrite covers the
# admin's CSS and JS too.
STATIC_URL = "/api/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# NB: the serverless filesystem is read-only and ephemeral, so MEDIA_ROOT is for
# local use only. User uploads need Vercel Blob or S3 before they are added.
MEDIA_URL = "/api/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- REST framework -------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env_str("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env_str("JWT_REFRESH_DAYS", "14"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": f"{SITE_NAME} API",
    "DESCRIPTION": "Shared backend facilities (auth, profiles, settings).",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
}

# --- Email ----------------------------------------------------------------

# Resend over SMTP, so Django's own backend does the sending. Without a key,
# mail is printed to the console, which is all local development needs.
RESEND_API_KEY = env_str("RESEND_API_KEY")
if RESEND_API_KEY:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.resend.com"
    # STARTTLS on 587: hosts such as Hetzner block outbound 465 (and 25).
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = "resend"
    EMAIL_HOST_PASSWORD = RESEND_API_KEY
    EMAIL_TIMEOUT = 10
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = formataddr((SITE_NAME, env_str("EMAIL_FROM_ADDRESS", "no-reply@localhost")))

# Where the frontend is served, for links in outgoing email.
PUBLIC_ORIGIN = env_str("PUBLIC_ORIGIN", "http://localhost:3000").rstrip("/")

# --- CORS -----------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", [])
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", DEBUG)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = (
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
)
CSRF_TRUSTED_ORIGINS = (
    env_list("CSRF_TRUSTED_ORIGINS", [])
    + [f"https://{host}" for host in VERCEL_HOSTS]
    + ([f"https://*{VERCEL_INTERNAL_HOST_SUFFIX}"] if ON_VERCEL else [])
)

# --- Security -------------------------------------------------------------

if not DEBUG:
    # The web server in front (Vercel's edge, or Caddy on our own box) terminates
    # TLS and forwards the original scheme.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Behind Caddy this stays off: Caddy does the http->https redirect itself, and
    # the frontend's internal calls to http://backend:8000 must not be bounced.
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(env_str("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Off only while the site is served over plain HTTP (a bare IP, no domain
    # yet): browsers silently drop Secure cookies on http://, breaking admin login.
    SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
