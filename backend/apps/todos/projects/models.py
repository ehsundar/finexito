"""A member's projects and the sections in them.

Projects nest, and a section belongs to one project. The rules live in each
model's ``clean()``, so the API and the admin enforce the same ones.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel

MAX_PROJECT_DEPTH = 3


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
            >= settings.TODOS_PROJECTS_MAX
        ):
            errors["name"] = _("You have reached the limit of %(max)s projects.") % {
                "max": settings.TODOS_PROJECTS_MAX
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
            >= settings.TODOS_PROJECTS_MAX_SECTIONS
        ):
            errors["project"] = _("A project holds up to %(max)s sections.") % {
                "max": settings.TODOS_PROJECTS_MAX_SECTIONS
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
