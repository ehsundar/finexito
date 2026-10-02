"""Accounts' settings, loaded into Django's by config/settings.py."""

from datetime import timedelta

from config.env import env_str

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env_str("ACCOUNTS_JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env_str("ACCOUNTS_JWT_REFRESH_DAYS", "14"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Sign in with Google: the OAuth client from the Google Cloud console. Its
# authorised redirect URI is {PUBLIC_ORIGIN}/auth/google/callback.
ACCOUNTS_GOOGLE_CLIENT_ID = env_str("ACCOUNTS_GOOGLE_CLIENT_ID")
ACCOUNTS_GOOGLE_CLIENT_SECRET = env_str("ACCOUNTS_GOOGLE_CLIENT_SECRET")
