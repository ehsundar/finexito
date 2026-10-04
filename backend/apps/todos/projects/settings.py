"""The todos projects app's settings, loaded into Django's by config/settings.py.

Limits only stop one account from hurting the server; real use never meets them.
"""

from config.env import env_int, env_str

TODOS_PROJECTS_MAX = env_int("TODOS_PROJECTS_MAX", 500)
TODOS_PROJECTS_MAX_SECTIONS = env_int("TODOS_PROJECTS_MAX_SECTIONS", 50)
# Writes across all the todos apps, per member; reads are free.
TODOS_PROJECTS_WRITE_RATE = env_str("TODOS_PROJECTS_WRITE_RATE", "1000/hour")
