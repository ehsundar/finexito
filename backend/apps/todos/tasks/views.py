from datetime import date, datetime, time, timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.db.models import Count, F, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reminders.models import Reminder, zone
from apps.todos.projects.views import TodosViewSet, WriteThrottle
from apps.todos.tasks.dates import Due
from apps.todos.tasks.filters import Filter
from apps.todos.tasks.models import FavouriteFilter, Label, Task, member_today, member_zone
from apps.todos.tasks.serializers import (
    DueParseSerializer,
    FilterSerializer,
    LabelSerializer,
    ReminderSerializer,
    TaskSerializer,
)


class LabelViewSet(TodosViewSet):
    serializer_class = LabelSerializer

    def rows(self):
        open_tasks = Q(tasks__completed_at__isnull=True, tasks__project__is_archived=False) & ~Q(
            tasks__section__is_archived=True
        )
        return (
            Label.objects.visible_to(self.request.user)
            .annotate(open_task_count=Count("tasks", filter=open_tasks))
            .order_by("order", "name")
        )

    def sibling_key(self, row):
        return row.owner_id

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(
    parameters=[
        OpenApiParameter("project", str),
        OpenApiParameter("section", str, description="A section id, or `none` for no section."),
        OpenApiParameter("parent", str, description="A task id, or `none` for the top level."),
        OpenApiParameter("label", str),
        OpenApiParameter("filter", str, description="A built-in filter's slug."),
        OpenApiParameter("q", str, description="Text in the content or description."),
        OpenApiParameter(
            "completed", bool, description="Completed tasks only, newest first. Default: open."
        ),
        OpenApiParameter(
            "view",
            str,
            enum=("today", "upcoming"),
            description="`today`: overdue and due today. `upcoming`: due `from` to `to`.",
        ),
        OpenApiParameter("from", date, description="For `view=upcoming`; default today."),
        OpenApiParameter("to", date, description="For `view=upcoming`; default a week on."),
    ]
)
class TaskViewSet(TodosViewSet):
    serializer_class = TaskSerializer

    def rows(self):
        user, params = self.request.user, self.request.query_params
        # Counting sub-tasks below groups the query, which drops Meta.ordering.
        tasks = Task.objects.visible_to(user).order_by("order", "created_at")
        if self.action == "list":
            if slug := params.get("filter"):
                if slug not in Filter.registry:
                    raise NotFound()
                tasks = Filter.registry[slug].queryset(user)
            elif view := params.get("view"):
                tasks = self.dated(tasks.open(), view)
            elif params.get("completed") in ("true", "1"):
                tasks = tasks.exclude(completed_at=None).order_by("-completed_at")
            elif not params.get("q"):
                tasks = tasks.open()
            for name in ("project", "section", "parent"):
                if value := params.get(name):
                    tasks = tasks.filter(**{name: None if value == "none" else value})
            if label := params.get("label"):
                tasks = tasks.filter(labels=label)
            if q := params.get("q"):
                tasks = tasks.filter(Q(content__icontains=q) | Q(description__icontains=q))
                # Grouped by project on the client; open tasks first.
                tasks = tasks.order_by(F("completed_at").asc(nulls_first=True), "order")
        return tasks.prefetch_related("labels").annotate(
            subtask_count=Count("subtasks", distinct=True),
            completed_subtask_count=Count(
                "subtasks", filter=Q(subtasks__completed_at__isnull=False), distinct=True
            ),
        )

    def dated(self, tasks, view):
        """Today: overdue oldest first, then today's, timed ones by time, then by
        priority and project. Upcoming: by day from ``from`` to ``to``."""
        user, params = self.request.user, self.request.query_params
        local, today = zone(member_zone(user)), member_today(user)
        if view == "today":
            first, last = None, today
        elif view == "upcoming":
            try:
                first = date.fromisoformat(params.get("from") or today.isoformat())
                last = date.fromisoformat(params["to"]) if params.get("to") else None
            except ValueError:
                raise ValidationError("Dates are YYYY-MM-DD.") from None
            last = last or first + timedelta(days=6)
            if (last - first).days > 92:
                raise ValidationError("Ask for up to three months at a time.")
        else:
            raise ValidationError("Unknown view.")
        end = datetime.combine(last + timedelta(days=1), time(), tzinfo=local)
        untimed = Q(due_at__isnull=True, due_date__lte=last)
        timed = Q(due_at__lt=end)
        if first:
            untimed &= Q(due_date__gte=first)
            timed &= Q(due_at__gte=datetime.combine(first, time(), tzinfo=local))
        return tasks.filter(untimed | timed).order_by(
            "due_date", F("due_at").asc(nulls_last=True), "priority", "project__order", "order"
        )

    def sibling_key(self, row):
        return (row.project_id, row.section_id, row.parent_id)

    def perform_create(self, serializer):
        task = serializer.save(created_by=self.request.user)
        task.tell_assignee(by=self.request.user)

    def perform_update(self, serializer):
        before = serializer.instance.assignee_id
        task = serializer.save()
        if task.assignee_id != before:
            task.tell_assignee(by=self.request.user)

    def get_object(self):
        task = self.rows().filter(pk=self.kwargs["pk"]).first()
        if task is None:
            raise NotFound()
        return task

    def respond(self, task, status_code=status.HTTP_200_OK):
        task = self.rows().get(pk=task.pk)
        return Response(
            TaskSerializer(task, context=self.get_serializer_context()).data, status=status_code
        )

    @extend_schema(request=None, responses=TaskSerializer)
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        task = self.get_object()
        task.close()
        return self.respond(task)

    @extend_schema(request=None, responses=TaskSerializer)
    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        task = self.get_object()
        task.reopen()
        return self.respond(task)

    @extend_schema(
        request=inline_serializer(
            "Reschedule",
            {
                "tasks": serializers.ListField(child=serializers.UUIDField()),
                "date": serializers.DateField(),
            },
        ),
        responses={204: None},
        description="Move tasks to a date, each keeping its time.",
    )
    @action(detail=False, methods=["post"])
    @transaction.atomic
    def reschedule(self, request):
        ids = serializers.ListField(child=serializers.UUIDField(), max_length=5000).run_validation(
            request.data.get("tasks")
        )
        day = serializers.DateField().run_validation(request.data.get("date"))
        tasks = list(self.rows().filter(pk__in=ids))
        if len(tasks) != len(set(ids)):
            raise NotFound()
        local = zone(member_zone(request.user))
        for task in tasks:
            if task.due_at:
                task.due_at = datetime.combine(day, task.due_at.astimezone(local).time(), local)
            if not task.due_rule:
                task.due_string = ""
            task.due_date = day
            task.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=ReminderSerializer, responses=ReminderSerializer(many=True))
    @action(detail=True, methods=["get", "post"])
    def reminders(self, request, pk=None):
        task = self.get_object()
        if request.method == "POST":
            serializer = ReminderSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                task.add_reminder(
                    request.user,
                    minutes_before=serializer.validated_data.get("minutes_before"),
                    at=serializer.validated_data.get("start_at"),
                )
            except ModelValidationError as error:
                raise ValidationError(error.messages) from None
        reminders = task.reminders.filter(user=request.user).order_by("start_at")
        code = status.HTTP_201_CREATED if request.method == "POST" else status.HTTP_200_OK
        return Response(ReminderSerializer(reminders, many=True).data, status=code)


class ReminderViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Removing one of a task's reminders."""

    serializer_class = ReminderSerializer
    throttle_classes = (WriteThrottle,)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Reminder.objects.none()
        mine = Task.objects.visible_to(self.request.user).values("pk")
        return Reminder.objects.filter(
            user=self.request.user,
            content_type=ContentType.objects.get_for_model(Task),
            object_id__in=mine,
        )


class DueDateParseView(APIView):
    """What a phrase means as a due date, for the date field's preview, and where
    one is in a task's text, for quick add's."""

    throttle_classes = ()

    @extend_schema(
        request=inline_serializer(
            "DueParse",
            {
                "text": serializers.CharField(max_length=500),
                "find": serializers.BooleanField(
                    default=False, help_text="Look for a phrase inside the text."
                ),
            },
        ),
        responses=DueParseSerializer,
    )
    def post(self, request):
        text = serializers.CharField(max_length=500, trim_whitespace=False).run_validation(
            request.data.get("text")
        )
        today = member_today(request.user)
        if request.data.get("find"):
            found = Due.find(text, today)
            if found is None:
                return Response(DueParseSerializer({"content": text}).data)
            due, span, rest = found
            return Response(DueParseSerializer({"due": due, "match": span, "content": rest}).data)
        try:
            due = Due.parse(text, today)
        except ValueError:
            raise ValidationError({"text": "Couldn't understand that date."}) from None
        return Response(DueParseSerializer({"due": due, "content": ""}).data)


class FilterViewSet(viewsets.GenericViewSet):
    """The built-in filters, and the caller's pins of them."""

    serializer_class = FilterSerializer
    queryset = FavouriteFilter.objects.none()
    pagination_class = None
    lookup_field = "slug"

    def list(self, request):
        pins = dict(request.user.todo_favourite_filters.values_list("slug", "order"))
        rows = [
            {
                "slug": f.slug,
                "name": f.name,
                "is_favourite": f.slug in pins,
                "order": pins.get(f.slug),
            }
            for f in Filter.registry.values()
        ]
        return Response(FilterSerializer(rows, many=True).data)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post", "delete"], throttle_classes=(WriteThrottle,))
    def favourite(self, request, slug=None):
        if slug not in Filter.registry:
            raise NotFound()
        pins = FavouriteFilter.objects.filter(owner=request.user)
        if request.method == "DELETE":
            pins.filter(slug=slug).delete()
        elif not pins.filter(slug=slug).exists():
            last = pins.order_by("-order").values_list("order", flat=True).first() or 0
            FavouriteFilter.objects.create(owner=request.user, slug=slug, order=last + 1)
        return Response(status=status.HTTP_204_NO_CONTENT)
