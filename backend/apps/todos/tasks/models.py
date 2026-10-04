"""A member's tasks, and the labels across them.

A task sits in a project, optionally in one of its sections, optionally under
another task. The rules live in ``Task.clean()``, so the API and the admin
enforce the same ones.
"""

import json
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower
from django.dispatch import receiver
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel
from apps.messaging.models import EmailMessage
from apps.reminders.models import Reminder, next_occurrence, reminder_due, zone
from apps.todos.projects.models import (
    Colour,
    Project,
    Section,
    TrackedModel,
    member_left,
    next_order,
)

MAX_TASK_DEPTH = 4


class LabelQuerySet(models.QuerySet):
    def visible_to(self, user):
        return self.filter(owner=user)


class Label(BaseModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todo_labels"
    )
    name = models.CharField(
        max_length=60,
        validators=[
            RegexValidator(r"^[\w-]+\Z", _("Use letters, digits, _ and - only, without spaces."))
        ],
    )
    colour = models.CharField(max_length=20, choices=Colour, default=Colour.NEUTRAL)
    is_favourite = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    objects = LabelQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        verbose_name = _("label")
        verbose_name_plural = _("labels")
        ordering = ("order", "name")
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "owner",
                name="todos_label_name_unique",
                violation_error_message=_("You already have a label with this name."),
            )
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        if (
            self._state.adding
            and Label.objects.filter(owner_id=self.owner_id).count()
            >= settings.TODOS_TASKS_MAX_LABELS
        ):
            raise ValidationError(
                _("You have reached the limit of %(max)s labels.")
                % {"max": settings.TODOS_TASKS_MAX_LABELS}
            )

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.order = next_order(Label.objects.filter(owner_id=self.owner_id))
        super().save(*args, **kwargs)


def member_zone(user) -> str:
    """The member's time zone name, from their profile; UTC without one."""
    profile = getattr(user, "profile", None)
    return profile.timezone if profile else "UTC"


def member_today(user) -> date:
    return tz.now().astimezone(zone(member_zone(user))).date()


# A member's preferences, kept in their profile's ``extra``.
REMINDER_DEFAULT_KEY = "todos_reminder_before"  # minutes, or "off"; default 30
REMINDER_EMAILS_KEY = "todos_reminder_emails"  # "false" turns them off
ASSIGNED_EMAILS_KEY = "todos_assigned_emails"  # "false" turns them off


def preference(user, key: str, default: str) -> str:
    profile = getattr(user, "profile", None)
    return (profile.extra if profile else {}).get(key, default)


class Priority(models.IntegerChoices):
    P1 = 1, _("Priority 1")
    P2 = 2, _("Priority 2")
    P3 = 3, _("Priority 3")
    P4 = 4, _("No priority")


class TaskQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Tasks in the member's projects, leaving out archived projects and sections."""
        return self.filter(
            project__in=Project.objects.visible_to(user), project__is_archived=False
        ).exclude(section__is_archived=True)

    def open(self):
        return self.filter(completed_at__isnull=True)

    def overdue(self, user):
        """Open tasks whose day has passed, or whose time has."""
        return self.open().filter(
            models.Q(due_at__isnull=True, due_date__lt=member_today(user))
            | models.Q(due_at__lt=tz.now())
        )


class Task(TrackedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    section = models.ForeignKey(
        Section, null=True, blank=True, on_delete=models.CASCADE, related_name="tasks"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="subtasks"
    )
    order = models.IntegerField(default=0)
    content = models.CharField(max_length=500, help_text=_("Inline Markdown."))
    description = models.TextField(max_length=16_000, blank=True, help_text=_("Markdown."))
    priority = models.PositiveSmallIntegerField(choices=Priority, default=Priority.P4)
    # Each person's own labels: on a shared task, everyone sees only theirs.
    labels = models.ManyToManyField(Label, blank=True, related_name="tasks")
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="todo_assigned_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )
    # Kept by the comments app, so lists can show it without counting.
    comment_count = models.PositiveIntegerField(default=0, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    # The day it's due, in the owner's time zone; with a time, also the instant,
    # which is what counts for a timed task.
    due_date = models.DateField(null=True, blank=True, db_index=True)
    due_at = models.DateTimeField(null=True, blank=True)
    due_string = models.CharField(max_length=200, blank=True, help_text=_("As typed."))
    due_rule = models.TextField(blank=True, help_text=_("DTSTART and RRULE, if it repeats."))
    due_from_completion = models.BooleanField(
        default=False, help_text=_("`every!`: the next date counts from completion.")
    )
    # A completed copy of a recurring task, one per completion.
    completion_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="completions",
        editable=False,
    )
    reminders = GenericRelation(Reminder)

    objects = TaskQuerySet.as_manager()

    class Meta(TrackedModel.Meta):
        verbose_name = _("task")
        verbose_name_plural = _("tasks")
        ordering = ("order", "created_at")
        indexes = [models.Index(fields=("project", "section", "parent", "order"))]

    def __str__(self) -> str:
        return self.content

    def ancestors(self) -> list["Task"]:
        chain, node = [], self.parent
        while node is not None:
            chain.append(node)
            node = node.parent
        return chain

    def descendant_ids(self) -> list:
        """Sub-tasks at every level, one query per level."""
        ids, level = [], [self.pk]
        while level := list(Task.objects.filter(parent_id__in=level).values_list("pk", flat=True)):
            ids += level
        return ids

    def levels_below(self) -> int:
        levels, level = 0, [self.pk]
        while level := list(Task.objects.filter(parent_id__in=level).values_list("pk", flat=True)):
            levels += 1
        return levels

    def clean(self):
        super().clean()
        self.content = self.content.strip()
        # A sub-task lives where its parent does. Nesting under a task brings this
        # one to its project and section; moving to another project or section
        # un-nests it, and a section left behind in the old project is dropped.
        if self.parent_id and self.changed("parent_id"):
            self.project_id, self.section_id = self.parent.project_id, self.parent.section_id
        elif self._state.adding:
            pass
        elif self.changed("project_id"):
            self.parent = None
            if self.section_id and self.section.project_id != self.project_id:
                self.section = None
        elif self.parent_id and self.changed("section_id"):
            self.parent = None
        people = self.project.people_ids()
        # Someone outside the project it moved to can't stay assigned.
        if self.assignee_id and self.changed("project_id") and self.assignee_id not in people:
            self.assignee = None

        errors = {}
        if self.assignee_id and self.assignee_id not in people:
            errors["assignee"] = _("Choose someone in this project.")
        if not self.content:
            errors["content"] = _("Write something.")
        if not isinstance(self.extra, dict):
            errors["extra"] = _("Must be a JSON object.")
        elif len(json.dumps(self.extra).encode()) > settings.TODOS_TASKS_MAX_EXTRA_BYTES:
            errors["extra"] = _("Keep this under %(max)s bytes.") % {
                "max": settings.TODOS_TASKS_MAX_EXTRA_BYTES
            }
        if self.section_id and self.section.project_id != self.project_id:
            errors["section"] = _("Choose a section in this task's project.")
        if self.due_at and not self.due_date:
            errors["due_date"] = _("A time needs a date.")
        if self.due_rule and not self.due_date:
            errors["due_date"] = _("A recurring task needs a date.")
        if self.parent_id:
            if self.parent.pk == self.pk or self.parent.pk in self.descendant_ids():
                errors["parent"] = _("A task can't go inside itself.")
            elif len(self.parent.ancestors()) + 2 + self.levels_below() > MAX_TASK_DEPTH:
                errors["parent"] = _("Tasks nest up to %(max)s levels.") % {"max": MAX_TASK_DEPTH}
        if (
            self.changed("project_id")
            and Task.objects.filter(project_id=self.project_id).exclude(pk=self.pk).open().count()
            >= settings.TODOS_TASKS_MAX_PER_PROJECT
        ):
            errors["project"] = _("A project holds up to %(max)s open tasks.") % {
                "max": settings.TODOS_TASKS_MAX_PER_PROJECT
            }
        if errors:
            raise ValidationError(errors)

    @property
    def owner(self):
        return self.project.owner

    def save(self, *args, **kwargs):
        moved = not self._state.adding and (
            self.changed("project_id") or self.changed("section_id")
        )
        redated = self.changed("due_date") or self.changed("due_at")
        was_timed = getattr(self, "_loaded", {}).get("due_at") is not None
        if not self.due_date:
            self.due_at, self.due_string, self.due_rule = None, "", ""
            self.due_from_completion = False
        # New tasks, and tasks moved somewhere new, go to the end.
        if self.changed("project_id") or self.changed("section_id") or self.changed("parent_id"):
            self.order = next_order(
                Task.objects.filter(
                    project_id=self.project_id, section_id=self.section_id, parent_id=self.parent_id
                )
            )
        super().save(*args, **kwargs)
        if moved:
            Task.objects.filter(pk__in=self.descendant_ids()).update(
                project_id=self.project_id, section_id=self.section_id, updated_at=tz.now()
            )
        if redated:
            self.follow_due(newly_timed=self.due_at is not None and not was_timed)

    def follow_due(self, newly_timed: bool):
        """Move relative reminders with the due time; no date, no reminders.

        A task that has just got a time gets the owner's default reminder.
        """
        if not self.due_date:
            self.reminders.all().delete()
            return
        for reminder in self.reminders.all():
            if (before := reminder.extra.get("minutes_before")) is None:
                continue
            if self.due_at is None:
                reminder.delete()
            else:
                reminder.start_at = self.due_at - timedelta(minutes=int(before))
                reminder.save()
        if newly_timed and self.completion_of_id is None and not self.reminders.exists():
            # On a shared project: the assignee, or everyone if no one is assigned.
            people = [self.assignee] if self.assignee else self.project_people()
            for user in people:
                default = preference(user, REMINDER_DEFAULT_KEY, "30")
                if default.isdigit():
                    self.add_reminder(user, minutes_before=int(default))

    def project_people(self) -> list:
        return list(get_user_model().objects.filter(pk__in=self.project.people_ids()))

    def add_reminder(self, user, minutes_before: int | None = None, at: datetime | None = None):
        """A reminder for ``user``, ``minutes_before`` the due time, or ``at`` a moment."""
        if self.reminders.filter(user=user).count() >= settings.TODOS_TASKS_MAX_REMINDERS:
            raise ValidationError(
                _("A task holds up to %(max)s reminders.")
                % {"max": settings.TODOS_TASKS_MAX_REMINDERS}
            )
        if minutes_before is not None:
            if self.due_at is None:
                raise ValidationError(_("Give the task a time first."))
            at = self.due_at - timedelta(minutes=minutes_before)
        return Reminder.objects.create(
            user=user,
            target=self,
            start_at=at,
            timezone=member_zone(user),
            extra={} if minutes_before is None else {"minutes_before": str(minutes_before)},
        )

    def next_due(self) -> datetime | None:
        """When a recurring task is next due, as the owner's wall-clock time.

        After the current due date, or after today if it's overdue or `every!`.
        None once the series has run out.
        """
        name = member_zone(self.owner)
        local = zone(name)
        now = tz.now().astimezone(local)
        current = self.due_at or datetime.combine(self.due_date, time(), tzinfo=local)
        rule = self.due_rule
        if self.due_from_completion:
            # Counted from today, at the task's time of day.
            rule = rule.split("\n")[-1]
            start = datetime.combine(now.date(), current.astimezone(local).time(), tzinfo=local)
            return next_occurrence(rule, name, start, start=start)
        if self.due_date < now.date():
            current = datetime.combine(now.date(), time.max, tzinfo=local)
        return next_occurrence(rule, name, current)

    def close(self):
        """Complete this task and its open sub-tasks.

        A recurring task stays open: a completed copy records the completion, the
        task moves to its next date, and its sub-tasks reopen with it.
        """
        if self.completed_at:
            return
        if self.due_rule and (upcoming := self.next_due()):
            self.complete_occurrence(upcoming)
            return
        now = tz.now()
        Task.objects.filter(pk__in=[self.pk, *self.descendant_ids()]).open().update(
            completed_at=now, updated_at=now
        )
        self.completed_at = now

    def complete_occurrence(self, upcoming: datetime):
        labels = list(self.labels.all())
        done = Task(
            project_id=self.project_id,
            section_id=self.section_id,
            parent_id=self.parent_id,
            content=self.content,
            description=self.description,
            priority=self.priority,
            assignee=self.assignee,
            created_by=self.created_by,
            due_date=self.due_date,
            due_at=self.due_at,
            due_string=self.due_string,
            completion_of=self,
            completed_at=tz.now(),
            extra=self.extra,
        )
        done.save()
        done.labels.set(labels)
        self.due_date = upcoming.date()
        self.due_at = upcoming if self.due_at else None
        self.save()
        Task.objects.filter(pk__in=self.descendant_ids()).update(
            completed_at=None, updated_at=tz.now()
        )

    def reopen(self):
        """Undo: reopen this task, the sub-tasks completed with it, and completed parents.

        For a recurring task, undo its last completion: back to that date.
        """
        if not self.completed_at:
            if last := self.completions.order_by("-completed_at").first():
                self.due_date, self.due_at = last.due_date, last.due_at
                self.save()
                last.delete()
            return
        together = Task.objects.filter(
            pk__in=self.descendant_ids(), completed_at=self.completed_at
        ).values_list("pk", flat=True)
        parents = [task.pk for task in self.ancestors() if task.completed_at]
        Task.objects.filter(pk__in=[self.pk, *together, *parents]).update(
            completed_at=None, updated_at=tz.now()
        )
        self.completed_at = None

    def tell_assignee(self, by):
        """Email the assignee that ``by`` gave them this task, unless they did it
        themselves or have opted out."""
        user = self.assignee
        if user is None or user == by or preference(user, ASSIGNED_EMAILS_KEY, "") == "false":
            return
        name = getattr(getattr(by, "profile", None), "display_name", "") or by.email
        lines = [f"{name} assigned you a task in {self.project.name}:", "", self.content]
        lines += ["", f"Open it: {settings.PUBLIC_ORIGIN}/todos/task?id={self.pk}"]
        lines += ["", f"— {settings.SITE_NAME}"]
        EmailMessage.objects.create(
            to=user.email,
            subject=f"Assigned to you: {self.content}",
            body="\n".join(lines),
            extra={"purpose": "todos_assigned", "task": str(self.pk)},
        )


class FavouriteFilter(BaseModel):
    """A member's pin of a built-in filter (``todos.filters``), shown in the sidebar."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todo_favourite_filters"
    )
    slug = models.SlugField(max_length=60)
    order = models.IntegerField(default=0)

    class Meta(BaseModel.Meta):
        verbose_name = _("favourite filter")
        verbose_name_plural = _("favourite filters")
        ordering = ("order", "created_at")
        constraints = [
            models.UniqueConstraint(fields=("owner", "slug"), name="todos_favourite_filter_unique")
        ]

    def __str__(self) -> str:
        return self.slug


@receiver(member_left)
def forget_member(sender, project, user, **kwargs):
    """Someone leaving takes their assignments, reminders and labels with them."""
    tasks = Task.objects.filter(project=project)
    tasks.filter(assignee=user).update(assignee=None, updated_at=tz.now())
    Reminder.objects.filter(
        user=user, content_type=ContentType.objects.get_for_model(Task), object_id__in=tasks
    ).delete()
    Task.labels.through.objects.filter(task__in=tasks, label__owner=user).delete()


@receiver(reminder_due)
def email_reminder(sender, reminder, **kwargs):
    """Email the reminder's member about the task, unless it's done or they've opted out."""
    task = reminder.target
    if not isinstance(task, Task) or task.completed_at:
        return
    user = reminder.user
    if preference(user, REMINDER_EMAILS_KEY, "") == "false":
        return
    local = zone(member_zone(user))
    when = (
        task.due_at.astimezone(local).strftime("%-d %b, %H:%M")
        if task.due_at
        else task.due_date.strftime("%-d %b")
        if task.due_date
        else ""
    )
    lines = [task.content, f"Due {when}" if when else None, f"In {task.project.name}"]
    lines += ["", f"Open it: {settings.PUBLIC_ORIGIN}/todos/task?id={task.pk}"]
    lines += ["", f"— {settings.SITE_NAME}"]
    EmailMessage.objects.create(
        to=user.email,
        subject=f"Reminder: {task.content}",
        body="\n".join(line for line in lines if line is not None),
        extra={"purpose": "todos_reminder", "task": str(task.pk)},
    )
