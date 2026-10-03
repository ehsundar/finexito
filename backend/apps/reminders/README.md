# reminders

Times at which to tell an app about one of its rows. Generic: it depends only
on `accounts` and knows nothing about what it reminds people of.

## Using it

Create a reminder pointing at the row; that is all:

```python
from apps.reminders.models import Reminder

Reminder.objects.create(user=member, target=task, start_at=when, timezone="Europe/London")
```

Then receive `reminder_due` and do what the reminder is for:

```python
from django.dispatch import receiver
from apps.reminders.models import reminder_due

@receiver(reminder_due)
def remind(sender, reminder, **kwargs):
    ...  # reminder.target is the row
```

`target` must have a UUID primary key (every `BaseModel` does).

## How it works

- `next_at` is the next time it fires; empty, with status `done`, once it has
  finished. Saving a new reminder, or a new `start_at`, `rule` or `timezone`,
  schedules it afresh.
- `rule` is an RRULE (`FREQ=WEEKLY;BYDAY=MO`) for one that repeats; times are
  wall-clock times in `timezone`, so summer time and month ends behave.
  `next_occurrence()` does that maths, and other apps reuse it.
- `manage.py fire_reminders`, run every minute by the `cron` container, fires
  what is due. Rows stay locked while they fire, so overlapping runs never fire
  one twice. After downtime each fires once, and moves on from now.
- A receiver that raises has its writes rolled back and marks the reminder
  `failed`, with the error; the others still fire. The admin retries failed ones,
  or fires any now.
- A member fires at most `REMINDERS_MAX_PER_HOUR` reminders (default 60) in an
  hour; the rest wait for a later run.
