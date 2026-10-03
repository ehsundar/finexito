
from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.todos.filters import Filter
from apps.todos.models import FavouriteFilter, Label, Project, Section, Task
from apps.todos.serializers import (
    FilterSerializer,
    LabelSerializer,
    ProjectSerializer,
    SectionSerializer,
    TaskSerializer,
)


class WriteThrottle(ScopedRateThrottle):
    """Caps writes per member at TODOS_WRITE_RATE; reads are free."""

    scope = "todos"

    def get_rate(self):
        return settings.TODOS_WRITE_RATE

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super(ScopedRateThrottle, self).allow_request(request, view)


class TodosViewSet(viewsets.ModelViewSet):
    """The caller's own rows; anyone else's are 404."""

    pagination_class = None
    throttle_classes = (WriteThrottle,)
    http_method_names = ("get", "post", "patch", "delete")

    def get_queryset(self):
        # The schema generator calls this without a member.
        if getattr(self, "swagger_fake_view", False):
            return self.serializer_class.Meta.model.objects.none()
        return self.rows()

    def rows(self):
        raise NotImplementedError

    def sibling_key(self, row):
        """What rows share when they are siblings, so only they reorder together."""
        raise NotImplementedError

    @extend_schema(
        request=serializers.ListSerializer(child=serializers.UUIDField()),
        responses={204: None},
        description="Put sibling rows in the order given.",
    )
    @action(detail=False, methods=["post"])
    def reorder(self, request):
        ids = serializers.ListField(child=serializers.UUIDField(), max_length=5000).run_validation(
            request.data
        )
        rows = {row.pk: row for row in self.get_queryset().filter(pk__in=ids)}
        if len(rows) != len(set(ids)):
            raise NotFound()
        if len({self.sibling_key(row) for row in rows.values()}) > 1:
            raise ValidationError("These aren't siblings.")
        for position, pk in enumerate(ids, start=1):
            rows[pk].order = position
        self.get_queryset().model.objects.bulk_update(rows.values(), ["order"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    parameters=[OpenApiParameter("archived", bool, description="Archived projects instead.")]
)
class ProjectViewSet(TodosViewSet):
    serializer_class = ProjectSerializer

    def rows(self):
        open_tasks = Q(tasks__completed_at__isnull=True) & ~Q(tasks__section__is_archived=True)
        # Counting groups the query, which drops Meta.ordering; hence order_by.
        projects = (
            Project.objects.visible_to(self.request.user)
            .annotate(open_task_count=Count("tasks", filter=open_tasks))
            .order_by("order", "created_at")
        )
        if self.action == "list":
            Project.objects.inbox(self.request.user)
            archived = self.request.query_params.get("archived") in ("true", "1")
            projects = projects.filter(is_archived=archived)
        return projects

    def sibling_key(self, row):
        return row.parent_id

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()


@extend_schema(
    parameters=[
        OpenApiParameter("project", str),
        OpenApiParameter("q", str, description="Text in the name."),
    ]
)
class SectionViewSet(TodosViewSet):
    serializer_class = SectionSerializer

    def rows(self):
        sections = Section.objects.visible_to(self.request.user)
        if project := self.request.query_params.get("project"):
            sections = sections.filter(project_id=project)
        if q := self.request.query_params.get("q"):
            sections = sections.filter(name__icontains=q)
        return sections

    def sibling_key(self, row):
        return row.project_id

    def get_object(self):
        # Archived sections stay reachable by id, so they can be unarchived.
        section = Section.objects.filter(
            pk=self.kwargs["pk"], project__owner=self.request.user
        ).first()
        if section is None:
            raise NotFound()
        return section


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

    def sibling_key(self, row):
        return (row.project_id, row.section_id, row.parent_id)

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
