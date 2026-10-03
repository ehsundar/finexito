"""The reminders app's settings, loaded into Django's by config/settings.py."""

from config.env import env_int

# Reminders one member can fire in an hour; the rest wait for the next run.
REMINDERS_MAX_PER_HOUR = env_int("REMINDERS_MAX_PER_HOUR", 60)
