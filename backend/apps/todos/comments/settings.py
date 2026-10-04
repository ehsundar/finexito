"""The todos comments app's settings, loaded into Django's by config/settings.py."""

from config.env import env_int, env_str

TODOS_COMMENTS_MAX_ATTACHMENT_BYTES = env_int("TODOS_COMMENTS_MAX_ATTACHMENT_BYTES", 25 * 1024**2)
# All of a member's attachments together.
TODOS_COMMENTS_MAX_STORAGE_BYTES = env_int("TODOS_COMMENTS_MAX_STORAGE_BYTES", 1024**3)
# New comments per member, so a script can't flood a project or anyone's inbox.
TODOS_COMMENTS_RATE = env_str("TODOS_COMMENTS_RATE", "120/hour")
# Comments on the same thing within this long go out as one email.
TODOS_COMMENTS_EMAIL_DELAY_MINUTES = env_int("TODOS_COMMENTS_EMAIL_DELAY_MINUTES", 5)
