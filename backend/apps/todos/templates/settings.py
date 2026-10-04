"""The todos templates app's settings, loaded into Django's by config/settings.py."""

from config.env import env_int, env_str

TODOS_TEMPLATES_MAX = env_int("TODOS_TEMPLATES_MAX", 100)
TODOS_TEMPLATES_MAX_TASKS = env_int("TODOS_TEMPLATES_MAX_TASKS", 1000)
# Comma-separated slugs of the built-in templates this deployment offers; blank for all.
TODOS_TEMPLATES_BUILT_IN = [s for s in env_str("TODOS_TEMPLATES_BUILT_IN", "").split(",") if s]
