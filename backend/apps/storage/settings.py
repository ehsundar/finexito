"""Storage's own settings, loaded into Django's by config/settings.py.

STORAGE_ROOT stays in config/settings.py, since Django's MEDIA_ROOT is built from it.
"""

from datetime import timedelta

from config.env import env_bool, env_int

# The largest file any ticket may allow. Caddy's limit in deploy/Caddyfile must match.
STORAGE_MAX_UPLOAD_BYTES = env_int("STORAGE_MAX_UPLOAD_BYTES", 25 * 1024 * 1024)
STORAGE_UPLOAD_TTL = timedelta(minutes=env_int("STORAGE_UPLOAD_TTL_MINUTES", 30))
# Behind Caddy, private files are handed over to it with X-Accel-Redirect
# rather than streamed through a gunicorn worker.
STORAGE_ACCEL_REDIRECT = env_bool("STORAGE_ACCEL_REDIRECT", False)
