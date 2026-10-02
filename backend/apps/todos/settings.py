"""The todos app's settings, loaded into Django's by config/settings.py.

Limits only stop one account from hurting the server; real use never meets them.
"""

from config.env import env_str

TODOS_MAX_PROJECTS = int(env_str("TODOS_MAX_PROJECTS", "500"))
TODOS_MAX_SECTIONS_PER_PROJECT = int(env_str("TODOS_MAX_SECTIONS_PER_PROJECT", "50"))
TODOS_MAX_TASKS_PER_PROJECT = int(env_str("TODOS_MAX_TASKS_PER_PROJECT", "5000"))
TODOS_MAX_LABELS = int(env_str("TODOS_MAX_LABELS", "500"))
TODOS_MAX_EXTRA_BYTES = int(env_str("TODOS_MAX_EXTRA_BYTES", str(16 * 1024)))
TODOS_WRITE_RATE = env_str("TODOS_WRITE_RATE", "1000/hour")
