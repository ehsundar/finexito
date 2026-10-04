"""A member's tasks: projects, the sections and tasks in them, and labels across them.

Each level is its own model with its own rules: projects nest, a section belongs
to one project, and a task sits in a project, optionally in one of its sections,
optionally under another task. The rules live in each model's ``clean()``, so the
API and the admin enforce the same ones.
"""

import json
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
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

MAX_PROJECT_DEPTH = 3
MAX_TASK_DEPTH = 4


class Colour(models.TextChoices):
    """Named, not hex: the frontend maps each name to a theme variable."""

    NEUTRAL = "neutral", _("Neutral")
    RED = "red", _("Red")
    ORANGE = "orange", _("Orange")
    YELLOW = "yellow", _("Yellow")
    GREEN = "green", _("Green")
    TEAL = "teal", _("Teal")
    BLUE = "blue", _("Blue")
    PURPLE = "purple", _("Purple")
    PINK = "pink", _("Pink")


class TrackedModel(BaseModel):
    """Remembers the values a row was loaded with, so ``save()`` can tell what moved."""

    class Meta(BaseModel.Meta):
        abstract = True

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._loaded = dict(zip(field_names, values, strict=True))
        return instance

    def changed(self, attname: str) -> bool:
        """Whether a field differs from the database; always true for a new row."""
        loaded = getattr(self, "_loaded", None)
        return loaded is None or loaded.get(attname) != getattr(self, attname)


def next_order(siblings) -> int:
    return (siblings.aggregate(models.Max("order"))["order__max"] or 0) + 1


class ProjectQuerySet(models.QuerySet):
    def visible_to(self, user):
        return self.filter(owner=user)

    def inbox(self, user) -> "Project":
        """The member's Inbox, made the first time it is asked for."""
        project, _created = self.get_or_create(
            owner=user, is_inbox=True, defaults={"name": "Inbox"}
        )
        return project


class ProjectView(models.TextChoices):
    LIST = "list", _("List")
    BOARD = "board", _("Board")


class ProjectSort(models.TextChoices):
    MANUAL = "manual", _("Manual")
    PRIORITY = "priority", _("Priority")
    NAME = "name", _("Name")
    ADDED = "added", _("Date added")


class Project(TrackedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todo_projects"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    name = models.CharField(max_length=120)
    colour = models.CharField(max_length=20, choices=Colour, default=Colour.NEUTRAL)
    is_inbox = models.BooleanField(default=False, editable=False)
    is_favourite = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    view = models.CharField(max_length=10, choices=ProjectView, default=ProjectView.LIST)
    sort = models.CharField(max_length=10, choices=ProjectSort, default=ProjectSort.MANUAL)
    order = models.IntegerField(default=0)

    objects = ProjectQuerySet.as_manager()

    class Meta(TrackedModel.Meta):
        verbose_name = _("project")
        verbose_name_plural = _("projects")
        ordering = ("order", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("owner",),
                condition=models.Q(is_inbox=True),
                name="todos_one_inbox_per_owner",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def ancestors(self) -> list["Project"]:
        chain, node = [], self.parent
        while node is not None:
            chain.append(node)
            node = node.parent
        return chain

    def descendant_ids(self) -> list:
        """Sub-projects at every level, one query per level."""
        ids, level = [], [self.pk]
        while level := list(
            Project.objects.filter(parent_id__in=level).values_list("pk", flat=True)
        ):
            ids += level
        return ids

    def levels_below(self) -> int:
        levels, level = 0, [self.pk]
        while level := list(
            Project.objects.filter(parent_id__in=level).values_list("pk", flat=True)
        ):
            levels += 1
        return levels

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        errors = {}
        if not self.name:
            errors["name"] = _("A project needs a name.")
        if self.is_inbox and not self._state.adding:
            if self.changed("name") or self.changed("parent_id") or self.changed("is_archived"):
                errors["name"] = _("The Inbox can't be renamed, archived or nested.")
        if self.parent_id:
            parent = self.parent
            if parent.owner_id != self.owner_id or parent.is_inbox:
                errors["parent"] = _("Choose one of your projects.")
            elif parent.pk == self.pk or parent.pk in self.descendant_ids():
                errors["parent"] = _("A project can't go inside itself.")
            elif len(parent.ancestors()) + 2 + self.levels_below() > MAX_PROJECT_DEPTH:
                errors["parent"] = _("Projects nest up to %(max)s levels.") % {
                    "max": MAX_PROJECT_DEPTH
                }
        if (
            self._state.adding
            and Project.objects.filter(owner_id=self.owner_id).count()
            >= settings.TODOS_MAX_PROJECTS
        ):
            errors["name"] = _("You have reached the limit of %(max)s projects.") % {
                "max": settings.TODOS_MAX_PROJECTS
            }
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.changed("parent_id"):
            self.order = next_order(
                Project.objects.filter(owner_id=self.owner_id, parent_id=self.parent_id)
            )
        cascade = not self._state.adding and self.changed("is_archived")
        super().save(*args, **kwargs)
        # Archiving takes the sub-projects with it; unarchiving brings them back.
        if cascade:
            Project.objects.filter(pk__in=self.descendant_ids()).update(
                is_archived=self.is_archived
            )

    def delete(self, *args, **kwargs):
        if self.is_inbox:
            raise ValidationError(_("The Inbox can't be deleted."))
        return super().delete(*args, **kwargs)


class SectionQuerySet(models.QuerySet):
    def visible_to(self, user):
        return self.filter(project__owner=user, project__is_archived=False, is_archived=False)


class Section(TrackedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=500)
    order = models.IntegerField(default=0)
    is_archived = models.BooleanField(default=False)

    objects = SectionQuerySet.as_manager()

    class Meta(TrackedModel.Meta):
        verbose_name = _("section")
        verbose_name_plural = _("sections")
        ordering = ("order", "created_at")

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        errors = {}
        if not self.name:
            errors["name"] = _("A section needs a name.")
        if (
            self.changed("project_id")
            and Section.objects.filter(project_id=self.project_id).exclude(pk=self.pk).count()
            >= settings.TODOS_MAX_SECTIONS_PER_PROJECT
        ):
            errors["project"] = _("A project holds up to %(max)s sections.") % {
                "max": settings.TODOS_MAX_SECTIONS_PER_PROJECT
            }
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        moved = not self._state.adding and self.changed("project_id")
        if self.changed("project_id"):
            self.order = next_order(Section.objects.filter(project_id=self.project_id))
        super().save(*args, **kwargs)
        # A section moves to another project with its tasks.
        if moved:
            self.tasks.update(project_id=self.project_id)


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
            and Label.objects.filter(owner_id=self.owner_id).count() >= settings.TODOS_MAX_LABELS
        ):
            raise ValidationError(
                _("You have reached the limit of %(max)s labels.")
                % {"max": settings.TODOS_MAX_LABELS}
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


# A member's reminder preferences, kept in their profile's ``extra``.
REMINDER_DEFAULT_KEY = "todos_reminder_before"  # minutes, or "off"; default 30
REMINDER_EMAILS_KEY = "todos_reminder_emails"  # "false" turns them off


class Priority(models.IntegerChoices):
    P1 = 1, _("Priority 1")
    P2 = 2, _("Priority 2")
    P3 = 3, _("Priority 3")
    P4 = 4, _("No priority")


class TaskQuerySet(models.QuerySet):
    def visible_to(self, user):
        """The member's tasks, leaving out archived projects and sections."""
        return self.filter(project__owner=user, project__is_archived=False).exclude(
            section__is_archived=True
        )

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
    labels = models.ManyToManyField(Label, blank=True, related_name="tasks")
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

        errors = {}
        if not self.content:
            errors["content"] = _("Write something.")
        if not isinstance(self.extra, dict):
            errors["extra"] = _("Must be a JSON object.")
        elif len(json.dumps(self.extra).encode()) > settings.TODOS_MAX_EXTRA_BYTES:
            errors["extra"] = _("Keep this under %(max)s bytes.") % {
                "max": settings.TODOS_MAX_EXTRA_BYTES
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
            >= settings.TODOS_MAX_TASKS_PER_PROJECT
        ):
            errors["project"] = _("A project holds up to %(max)s open tasks.") % {
                "max": settings.TODOS_MAX_TASKS_PER_PROJECT
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
                project_id=self.project_id, section_id=self.section_id
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
        if newly_timed and self.completion_of_id is None:
            profile = getattr(self.owner, "profile", None)
            default = (profile.extra if profile else {}).get(REMINDER_DEFAULT_KEY, "30")
            if default.isdigit() and not self.reminders.exists():
                self.add_reminder(minutes_before=int(default))

    def add_reminder(self, minutes_before: int | None = None, at: datetime | None = None):
        """A reminder ``minutes_before`` the due time, or ``at`` a moment."""
        if self.reminders.count() >= settings.TODOS_MAX_REMINDERS_PER_TASK:
            raise ValidationError(
                _("A task holds up to %(max)s reminders.")
                % {"max": settings.TODOS_MAX_REMINDERS_PER_TASK}
            )
        if minutes_before is not None:
            if self.due_at is None:
                raise ValidationError(_("Give the task a time first."))
            at = self.due_at - timedelta(minutes=minutes_before)
        return Reminder.objects.create(
            user=self.owner,
            target=self,
            start_at=at,
            timezone=member_zone(self.owner),
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


@receiver(reminder_due)
def email_reminder(sender, reminder, **kwargs):
    """Email the owner about their task, unless it's done or they've opted out."""
    task = reminder.target
    if not isinstance(task, Task) or task.completed_at:
        return
    owner = task.owner
    profile = getattr(owner, "profile", None)
    if profile and profile.extra.get(REMINDER_EMAILS_KEY) == "false":
        return
    local = zone(member_zone(owner))
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
        to=owner.email,
        subject=f"Reminder: {task.content}",
        body="\n".join(line for line in lines if line is not None),
        extra={"purpose": "todos_reminder", "task": str(task.pk)},
    )
