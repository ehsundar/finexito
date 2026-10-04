"""Built-in filters: read-only views over a member's tasks.

Filters are code, not data. Adding one means adding a subclass of ``Filter``;
it registers itself under its slug.
"""

from datetime import timedelta

from django.utils import timezone as tz

from apps.todos.tasks.models import Priority, Task, member_today


class Filter:
    slug: str
    name: str
    registry: dict[str, "Filter"] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Filter.registry[cls.slug] = cls()

    def tasks(self, user):
        return Task.objects.visible_to(user).order_by("order", "created_at")

    def queryset(self, user):
        raise NotImplementedError


class PriorityOne(Filter):
    slug, name = "priority-1", "Priority 1"

    def queryset(self, user):
        return self.tasks(user).open().filter(priority=Priority.P1)


class PriorityTwo(Filter):
    slug, name = "priority-2", "Priority 2"

    def queryset(self, user):
        return self.tasks(user).open().filter(priority=Priority.P2)


class NoLabels(Filter):
    slug, name = "no-labels", "No labels"

    def queryset(self, user):
        return self.tasks(user).open().filter(labels__isnull=True)


class RecentlyCompleted(Filter):
    slug, name = "recently-completed", "Recently completed"

    def queryset(self, user):
        since = tz.now() - timedelta(days=7)
        return self.tasks(user).filter(completed_at__gte=since).order_by("-completed_at")


class Overdue(Filter):
    slug, name = "overdue", "Overdue"

    def queryset(self, user):
        return self.tasks(user).overdue(user).order_by("due_date", "due_at", "priority")


class NextSevenDays(Filter):
    slug, name = "next-7-days", "Next 7 days"

    def queryset(self, user):
        today = member_today(user)
        return (
            self.tasks(user)
            .open()
            .filter(due_date__gte=today, due_date__lt=today + timedelta(days=7))
            .order_by("due_date", "due_at", "priority")
        )


class NoDueDate(Filter):
    slug, name = "no-due-date", "No due date"

    def queryset(self, user):
        return self.tasks(user).open().filter(due_date__isnull=True)


class Recurring(Filter):
    slug, name = "recurring", "Recurring"

    def queryset(self, user):
        return self.tasks(user).open().exclude(due_rule="").order_by("due_date", "due_at")
