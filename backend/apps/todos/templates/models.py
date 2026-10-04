"""Templates: a project's structure, to start new projects from or add to old ones.

A template is a list of rows, the same as its CSV file, one per line:

- ``{"type": "section", "content": "Packing"}`` starts a section; the tasks after
  it go in it.
- ``{"type": "task", "content": …, "description": …, "priority": 1–4,
  "indent": 1–4, "labels": "space separated names", "due": …}``. A task indented
  one more than the one above is its sub-task. ``due`` is an offset from the day
  the template is applied, ``+3`` or ``+3 09:00``, or a recurrence phrase,
  ``every monday``.

Built-in templates are code (``templates.builtin``); a member's own are rows here.
"""

import csv
import io
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel
from apps.reminders.models import zone
from apps.todos.projects.models import Project, Section
from apps.todos.tasks.dates import Due
from apps.todos.tasks.models import Label, Task, member_today, member_zone

COLUMNS = ("type", "content", "description", "priority", "indent", "labels", "due")


def clean_rows(rows) -> list[dict]:
    """Rows as stored, or a ValidationError saying which line is wrong."""
    if not isinstance(rows, list):
        raise ValidationError(_("A template is a list of rows."))
    cleaned, depth, tasks = [], 0, 0
    for line, row in enumerate(rows, start=1):
        try:
            kind = row.get("type") or "task"
            content = str(row.get("content", "")).strip()
            if kind not in ("section", "task") or not content:
                raise ValueError
            if kind == "section":
                cleaned.append({"type": "section", "content": content[:500]})
                depth = 0
                continue
            indent = int(row.get("indent") or 1)
            priority = int(row.get("priority") or 4)
            if not 1 <= indent <= min(depth + 1, 4) or not 1 <= priority <= 4:
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            message = _("Line %(line)s isn't a section or a task.") % {"line": line}
            raise ValidationError(message) from None
        depth, tasks = indent, tasks + 1
        cleaned.append(
            {
                "type": "task",
                "content": content[:500],
                "description": str(row.get("description") or "")[:16_000],
                "priority": priority,
                "indent": indent,
                "labels": " ".join(str(row.get("labels") or "").split()),
                "due": str(row.get("due") or "").strip()[:200],
            }
        )
    if tasks > settings.TODOS_TEMPLATES_MAX_TASKS:
        raise ValidationError(
            _("A template holds up to %(max)s tasks.") % {"max": settings.TODOS_TEMPLATES_MAX_TASKS}
        )
    return cleaned


def snapshot(project: Project, user) -> list[dict]:
    """A project's open tasks and sections as rows; dates become offsets from today.

    Labels are the member's own; comments, assignees and reminders stay behind.
    """
    today = member_today(user)
    local = zone(member_zone(user))
    tasks = list(project.tasks.open().filter(completion_of=None).prefetch_related("labels"))

    def branch(parent, section, indent):
        level = [t for t in tasks if t.parent_id == parent and (parent or t.section_id == section)]
        for task in sorted(level, key=lambda t: (t.order, t.created_at)):
            due = task.due_string if task.due_rule else ""
            if task.due_date and not task.due_rule:
                due = f"+{max((task.due_date - today).days, 0)}"
                if task.due_at:
                    due += task.due_at.astimezone(local).strftime(" %H:%M")
            names = [label.name for label in task.labels.all() if label.owner_id == user.pk]
            yield {
                "type": "task",
                "content": task.content,
                "description": task.description,
                "priority": task.priority,
                "indent": indent,
                "labels": " ".join(names),
                "due": due,
            }
            yield from branch(task.pk, section, indent + 1)

    rows = list(branch(None, None, 1))
    for section in project.sections.filter(is_archived=False):
        rows.append({"type": "section", "content": section.name})
        rows += branch(None, section.pk, 1)
    return clean_rows(rows)


@transaction.atomic
def apply(rows: list[dict], user, project: Project | None = None, name: str = "") -> Project:
    """Create the rows, as a new project named ``name`` or at the end of ``project``.

    All or nothing: a row breaking a limit undoes everything before it.
    """
    if project is None:
        project = Project(owner=user, name=name)
        project.full_clean()
        project.save()
    today = member_today(user)
    local = zone(member_zone(user))
    labels = {label.name.lower(): label for label in Label.objects.filter(owner=user)}
    section, parents = None, {}
    for row in rows:
        if row["type"] == "section":
            section = Section(project=project, name=row["content"])
            section.full_clean()
            section.save()
            parents = {}
            continue
        parent = parents.get(row["indent"] - 1)
        task = Task(
            project=project,
            section=section,
            parent=parent,
            content=row["content"],
            description=row["description"],
            priority=row["priority"],
            created_by=user,
        )
        due = row["due"]
        if due.startswith("+"):
            days, _space, at = due[1:].partition(" ")
            try:
                task.due_date = today + timedelta(days=int(days))
                if at:
                    task.due_at = datetime.combine(task.due_date, time.fromisoformat(at), local)
            except ValueError:
                raise ValidationError(_("“%(due)s” isn't a date offset.") % {"due": due}) from None
        elif due:
            try:
                parsed = Due.parse(due, today)
            except ValueError:
                raise ValidationError(_("Couldn't understand “%(due)s”.") % {"due": due}) from None
            task.due_date, task.due_string = parsed.date, parsed.string
            task.due_rule, task.due_from_completion = parsed.rule, parsed.from_completion
            if parsed.time:
                task.due_at = datetime.combine(parsed.date, parsed.time, local)
        task.full_clean()
        task.save()
        mine = []
        for label_name in row["labels"].split():
            if label_name.lower() not in labels:
                label = Label(owner=user, name=label_name)
                label.full_clean()
                label.save()
                labels[label_name.lower()] = label
            mine.append(labels[label_name.lower()])
        task.labels.set(mine)
        parents = {depth: t for depth, t in parents.items() if depth < row["indent"]}
        parents[row["indent"]] = task
    return project


def to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def from_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    columns = {name.strip().lower() for name in reader.fieldnames or ()}
    if not {"type", "content"} <= columns:
        raise ValidationError(_("The file needs at least the columns type and content."))
    return clean_rows([{k.strip().lower(): v for k, v in row.items() if k} for row in reader])


class Template(BaseModel):
    """A member's own template: a snapshot, unchanged by later edits to its project."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todo_templates"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(max_length=2000, blank=True)
    rows = models.JSONField(default=list, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = _("template")
        verbose_name_plural = _("templates")
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": _("A template needs a name.")})
        self.rows = clean_rows(self.rows)
        if (
            self._state.adding
            and Template.objects.filter(owner_id=self.owner_id).count()
            >= settings.TODOS_TEMPLATES_MAX
        ):
            raise ValidationError(
                _("You have reached the limit of %(max)s templates.")
                % {"max": settings.TODOS_TEMPLATES_MAX}
            )
