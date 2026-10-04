"""Storage's own settings, loaded into Django's by config/settings.py.

STORAGE_ROOT stays in config/settings.py, since Django's MEDIA_ROOT is built from it.
"""

from datetime import timedelta

from config.env import env_bool, env_int, env_str

# The largest file any ticket may allow. Caddy's limit in deploy/Caddyfile must match.
STORAGE_MAX_UPLOAD_BYTES = env_int("STORAGE_MAX_UPLOAD_BYTES", 25 * 1024 * 1024)
STORAGE_UPLOAD_TTL = timedelta(minutes=env_int("STORAGE_UPLOAD_TTL_MINUTES", 30))
# Behind Caddy, private files are handed over to it with X-Accel-Redirect
# rather than streamed through a gunicorn worker.
STORAGE_ACCEL_REDIRECT = env_bool("STORAGE_ACCEL_REDIRECT", False)

# Every place a file can live, by a name each StoredObject keeps. Retire a
# location only once no row names it; old rows stay where they were put.
_bucket = {
    "region_name": env_str("STORAGE_REGION", "auto"),
    "endpoint_url": env_str("STORAGE_ENDPOINT_URL", ""),
    "access_key": env_str("STORAGE_ACCESS_KEY_ID", ""),
    "secret_key": env_str("STORAGE_SECRET_ACCESS_KEY", ""),
}
STORAGE_LOCATIONS = {
    "local-public": {
        "BACKEND": "apps.storage.backends.LocalStorage",
        "OPTIONS": {"directory": "public", "public": True},
    },
    "local-private": {
        "BACKEND": "apps.storage.backends.LocalStorage",
        "OPTIONS": {"directory": "private", "public": False},
    },
    "bucket-public": {
        "BACKEND": "apps.storage.backends.BucketStorage",
        "OPTIONS": {
            **_bucket,
            "bucket_name": env_str("STORAGE_PUBLIC_BUCKET", ""),
            "custom_domain": env_str("STORAGE_PUBLIC_DOMAIN", ""),
            "querystring_auth": False,
        },
    },
    "bucket-private": {
        "BACKEND": "apps.storage.backends.BucketStorage",
        "OPTIONS": {**_bucket, "bucket_name": env_str("STORAGE_PRIVATE_BUCKET", "")},
    },
}

# The classes an app picks from when it opens a ticket, and where each puts new
# files: a bucket once one is configured, the server's disk until then.
STORAGE_CLASSES = {
    "public": "bucket-public" if env_str("STORAGE_PUBLIC_BUCKET", "") else "local-public",
    "private": "bucket-private" if env_str("STORAGE_PRIVATE_BUCKET", "") else "local-private",
}
