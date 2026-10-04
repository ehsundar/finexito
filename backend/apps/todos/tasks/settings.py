"""The todos tasks app's settings, loaded into Django's by config/settings.py.

Limits only stop one account from hurting the server; real use never meets them.
"""

from config.env import env_int

TODOS_TASKS_MAX_PER_PROJECT = env_int("TODOS_TASKS_MAX_PER_PROJECT", 5000)
TODOS_TASKS_MAX_LABELS = env_int("TODOS_TASKS_MAX_LABELS", 500)
TODOS_TASKS_MAX_EXTRA_BYTES = env_int("TODOS_TASKS_MAX_EXTRA_BYTES", 16 * 1024)
TODOS_TASKS_MAX_REMINDERS = env_int("TODOS_TASKS_MAX_REMINDERS", 10)
