"""Django settings for the platform backend.

A single settings module driven by environment variables. Each app built on the
platform is its own deployment, configured through these variables.
"""

from email.utils import formataddr
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

from config.env import env_bool, env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent

# Local config. In production the environment comes from deploy/compose.yml,
# which also pins DEBUG off and refuses to start without a secret key.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = env_str("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DEBUG", True)

# --- Identity ---------------------------------------------------------------

# Each deployment is its own white-labelled product built from the same apps.
# Everything that names it to people (emails, the admin, the API docs, the
# frontend via /api/v1/manifest.webmanifest) reads this rather than spelling out a name.
SITE_NAME = env_str("SITE_NAME", "ehsundar")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ["*"] if DEBUG else [])

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
    "django_tasks_db",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.profiles",
    "apps.content",
    "apps.storage",
    "apps.messaging",
    "apps.reminders",
    "apps.todos.projects",
    "apps.todos.tasks",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Each app's own settings, under names it prefixes itself (STORAGE_*) or a
# package's own name (SIMPLE_JWT). Removing an app means removing its line here.
from apps.accounts.settings import *  # noqa: E402, F403
from apps.common.settings import *  # noqa: E402, F403
from apps.content.settings import *  # noqa: E402, F403
from apps.messaging.settings import *  # noqa: E402, F403
from apps.profiles.settings import *  # noqa: E402, F403
from apps.reminders.settings import *  # noqa: E402, F403
from apps.storage.settings import *  # noqa: E402, F403
from apps.todos.projects.settings import *  # noqa: E402, F403
from apps.todos.tasks.settings import *  # noqa: E402, F403

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Serves the collected static files (the admin's CSS and JS) from gunicorn.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
# A synchronous app, served by gunicorn; it deliberately declares WSGI only.
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
DATABASE_URL = env_str("DATABASE_URL", LOCAL_DATABASE_URL)

DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, conn_health_checks=True)
}

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

# Collected into the image at build time and served by WhiteNoise. Kept under
# /api/ with everything else, so Caddy's one /api/ route covers the admin's CSS
# and JS too.
STATIC_URL = "/api/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Uploads, handled by apps.storage. STORAGE_ROOT holds `public/`, served as is
# under MEDIA_URL (by Caddy in production, by runserver locally), `private/`,
# only reachable through signed links, and `tmp/` for uploads in progress.
# In production it is a directory on the server's disk; see deploy/compose.yml.
STORAGE_ROOT = Path(env_str("STORAGE_ROOT", str(BASE_DIR / "media")))
MEDIA_URL = "/api/media/"
MEDIA_ROOT = STORAGE_ROOT / "public"
# Storage's other settings are in apps/storage/settings.py.

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

SPECTACULAR_SETTINGS = {
    "TITLE": f"{SITE_NAME} API",
    "DESCRIPTION": "Shared backend facilities (auth, profiles, settings).",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    # Separate request types, so read-only fields aren't required when writing.
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Email ----------------------------------------------------------------

# Resend over SMTP, so Django's own backend does the sending; the password is a
# Resend API key. Without one, mail is printed to the console, which is all local
# development needs.
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD")
if EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.resend.com"
    # STARTTLS on 587: hosts such as Hetzner block outbound 465 (and 25).
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = "resend"
    EMAIL_TIMEOUT = 10
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = formataddr(
    (SITE_NAME, env_str("MESSAGING_FROM_ADDRESS", "no-reply@localhost"))
)

# Where the frontend is served, for links in outgoing email and OAuth redirects.
PUBLIC_ORIGIN = env_str("PUBLIC_ORIGIN", "http://localhost:3000").rstrip("/")

# --- Background tasks -----------------------------------------------------

# django.tasks, queued in Postgres by django-tasks-db and run by
# `manage.py db_worker`.
TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}

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
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])

# --- Security -------------------------------------------------------------

if not DEBUG:
    # Caddy, in front, terminates
    # TLS and forwards the original scheme.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Behind Caddy this stays off: Caddy does the http->https redirect itself, and
    # its proxied calls and the healthcheck reach http://backend:8000 directly.
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Off only while the site is served over plain HTTP (a bare IP, no domain
    # yet): browsers silently drop Secure cookies on http://, breaking admin login.
    SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
