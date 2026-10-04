from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.todos.projects.models import Project, Section
from apps.todos.projects.serializers import ProjectSerializer, SectionSerializer


class WriteThrottle(ScopedRateThrottle):
    """Caps writes per member at TODOS_PROJECTS_WRITE_RATE; reads are free."""

    scope = "todos"

    def get_rate(self):
        return settings.TODOS_PROJECTS_WRITE_RATE

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
