"""A member's tasks: projects, the sections and tasks in them, and labels across them.

Each level is its own model with its own rules: projects nest, a section belongs
to one project, and a task sits in a project, optionally in one of its sections,
optionally under another task. The rules live in each model's ``clean()``, so the
API and the admin enforce the same ones.
"""

import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel

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

    def save(self, *args, **kwargs):
        moved = not self._state.adding and (
            self.changed("project_id") or self.changed("section_id")
        )
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

    def close(self):
        """Complete this task and its open sub-tasks."""
        if self.completed_at:
            return
        now = tz.now()
        Task.objects.filter(pk__in=[self.pk, *self.descendant_ids()]).open().update(
            completed_at=now, updated_at=now
        )
        self.completed_at = now

    def reopen(self):
        """Undo: reopen this task, the sub-tasks completed with it, and completed parents."""
        if not self.completed_at:
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
