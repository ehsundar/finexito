"""The Google Calendar app's settings, loaded into Django's by config/settings.py.

It uses the Google client that sign-in does (ACCOUNTS_GOOGLE_CLIENT_ID and
_SECRET); the Calendar API must be on in that Google Cloud project.
"""

from config.env import env_int

TODOS_GOOGLE_EVENT_MINUTES = env_int("TODOS_GOOGLE_EVENT_MINUTES", 30)
