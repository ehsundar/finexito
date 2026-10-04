"""The todos sync app's settings, loaded into Django's by config/settings.py."""

from config.env import env_int

# How long deletions are remembered; a client last synced before that reloads everything.
TODOS_SYNC_TOMBSTONE_DAYS = env_int("TODOS_SYNC_TOMBSTONE_DAYS", 30)
# Operations in one POST.
TODOS_SYNC_MAX_OPERATIONS = env_int("TODOS_SYNC_MAX_OPERATIONS", 200)
