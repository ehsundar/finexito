"""Reminders: a time, or a series of times, at which to tell an app about one of its rows.

The app knows nothing about what it reminds people of. A reminder points at any
row (a generic foreign key); when it fires it sends ``reminder_due``, and the
app that owns the row decides what to do.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.dispatch import Signal
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel

# Sent with ``reminder=`` when a reminder fires. Raising marks it failed.
reminder_due = Signal()


def zone(name: str) -> ZoneInfo:
    """The named time zone, or UTC if there is no such zone."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def next_occurrence(rule: str, timezone: str, after: datetime, start: datetime | None = None):
    """The first time ``rule`` (RFC 5545 text) gives strictly after ``after``, or None.

    Occurrences are wall-clock times in ``timezone``, so a daily 9:00 stays at 9:00
    across a change to summer time, and "the 31st" skips shorter months. ``start``
    is the series' first time, unless ``rule`` carries its own DTSTART.
    """
    local = zone(timezone)
    wall = after.astimezone(local).replace(tzinfo=None)
    if start is not None:
        start = start.astimezone(local).replace(tzinfo=None)
    found = rrulestr(rule, dtstart=start).after(wall)
    return found.replace(tzinfo=local) if found else None


class ReminderStatus(models.TextChoices):
    SCHEDULED = "scheduled", _("Scheduled")
    DONE = "done", _("Done")
    FAILED = "failed", _("Failed")


class Reminder(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminders"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    target = GenericForeignKey("content_type", "object_id")
    start_at = models.DateTimeField(help_text=_("The first time it fires."))
    timezone = models.CharField(max_length=64, default="UTC")
    rule = models.TextField(blank=True, help_text=_("An RRULE, for one that repeats."))
    next_at = models.DateTimeField(null=True, blank=True, db_index=True, editable=False)
    status = models.CharField(
        max_length=20, choices=ReminderStatus, default=ReminderStatus.SCHEDULED, editable=False
    )
    fired_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_error = models.TextField(blank=True, editable=False)

    class Meta(BaseModel.Meta):
        verbose_name = _("reminder")
        verbose_name_plural = _("reminders")
        ordering = ("next_at", "start_at")
        indexes = [models.Index(fields=("content_type", "object_id"))]

    def __str__(self) -> str:
        return f"{self.content_type.model} {self.object_id} at {self.next_at or self.start_at}"

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._schedule = (instance.start_at, instance.rule, instance.timezone)
        return instance

    def save(self, *args, **kwargs):
        # A new time or rule schedules it afresh; firing leaves these alone.
        if getattr(self, "_schedule", None) != (self.start_at, self.rule, self.timezone):
            self.schedule(after=tz.now() - timedelta(microseconds=1))
            self._schedule = (self.start_at, self.rule, self.timezone)
        super().save(*args, **kwargs)

    def schedule(self, after: datetime) -> None:
        """Point ``next_at`` at the first time after ``after``, or finish."""
        if self.rule:
            self.next_at = next_occurrence(self.rule, self.timezone, after, start=self.start_at)
        else:
            self.next_at = self.start_at if self.start_at > after else None
        self.status = ReminderStatus.SCHEDULED if self.next_at else ReminderStatus.DONE

    def fire(self) -> None:
        """Send ``reminder_due``, then move on to the next time after now.

        After downtime that is one firing, however many times were missed. A
        receiver that raises has its writes undone and marks the reminder failed.
        """
        now = tz.now()
        try:
            with transaction.atomic():
                reminder_due.send(sender=Reminder, reminder=self)
        except Exception as exc:
            self.status = ReminderStatus.FAILED
            self.last_error = f"{type(exc).__name__}: {exc}"
        else:
            self.fired_at, self.last_error = now, ""
            self.schedule(after=now)
        self.save()

    def retry(self) -> None:
        """Fire a failed reminder again on the next run."""
        self.status, self.next_at = ReminderStatus.SCHEDULED, tz.now()
        self.save()

    @classmethod
    def fire_due(cls) -> int:
        """Fire every reminder whose time has come; returns how many fired.

        The rows stay locked while they fire, so an overlapping run skips them. A
        member over REMINDERS_MAX_PER_HOUR waits for a later run.
        """
        now = tz.now()
        fired = 0
        with transaction.atomic():
            due = cls.objects.select_for_update(skip_locked=True).filter(
                status=ReminderStatus.SCHEDULED, next_at__lte=now
            )
            recent = dict(
                cls.objects.filter(fired_at__gt=now - timedelta(hours=1))
                .values("user")
                .annotate(n=models.Count("pk"))
                .values_list("user", "n")
            )
            for reminder in due.order_by("next_at"):
                if recent.get(reminder.user_id, 0) >= settings.REMINDERS_MAX_PER_HOUR:
                    continue
                reminder.fire()
                if reminder.status != ReminderStatus.FAILED:
                    recent[reminder.user_id] = recent.get(reminder.user_id, 0) + 1
                    fired += 1
        return fired
