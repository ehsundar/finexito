from django.conf import settings
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.db.models import Case, Count, F, OuterRef, Prefetch, Q, Subquery, When
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import SAFE_METHODS, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.todos.projects.models import Project, ProjectMember, Section, new_invite_token
from apps.todos.projects.serializers import (
    InviteLinkSerializer,
    JoinPreviewSerializer,
    PersonSerializer,
    ProjectSerializer,
    SectionSerializer,
)


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
    """Rows the caller can see; anything else is 404."""

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


def owned(project, user):
    """Refuse what only the project's owner may do."""
    if project.owner_id != user.pk:
        raise PermissionDenied("Only the project's owner can do that.")
    return project


@extend_schema(
    parameters=[OpenApiParameter("archived", bool, description="Archived projects instead.")]
)
class ProjectViewSet(TodosViewSet):
    serializer_class = ProjectSerializer

    def rows(self):
        user = self.request.user
        open_tasks = Q(tasks__completed_at__isnull=True) & ~Q(tasks__section__is_archived=True)
        mine = ProjectMember.objects.filter(project=OuterRef("pk"), user=user)
        # Counting groups the query, which drops Meta.ordering; hence order_by.
        projects = (
            Project.objects.visible_to(user)
            .annotate(
                open_task_count=Count("tasks", filter=open_tasks, distinct=True),
                member_count=Count("members", distinct=True),
                place=Case(
                    When(owner=user, then=F("order")), default=Subquery(mine.values("order"))
                ),
            )
            .prefetch_related(Prefetch("members", ProjectMember.objects.filter(user=user), "mine"))
            .order_by("place", "created_at")
        )
        if self.action == "list":
            Project.objects.inbox(user)
            archived = self.request.query_params.get("archived") in ("true", "1")
            projects = projects.filter(is_archived=archived)
        return projects

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @transaction.atomic
    def perform_destroy(self, instance):
        owned(instance, self.request.user).delete()

    @extend_schema(
        request=serializers.ListSerializer(child=serializers.UUIDField()),
        responses={204: None},
        description="Put sibling projects in the order given, as the caller places them.",
    )
    @action(detail=False, methods=["post"])
    @transaction.atomic
    def reorder(self, request):
        ids = serializers.ListField(child=serializers.UUIDField(), max_length=5000).run_validation(
            request.data
        )
        rows = {row.pk: row for row in self.get_queryset().filter(pk__in=ids)}
        if len(rows) != len(set(ids)):
            raise NotFound()
        places = {pk: row.mine[0] if row.mine else row for pk, row in rows.items()}
        if len({place.parent_id for place in places.values()}) > 1:
            raise ValidationError("These aren't siblings.")
        for position, pk in enumerate(ids, start=1):
            places[pk].order = position
        for model in (Project, ProjectMember):
            model.objects.bulk_update([p for p in places.values() if type(p) is model], ["order"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses=PersonSerializer(many=True))
    @action(detail=True, methods=["get"])
    def collaborators(self, request, pk=None):
        """The owner first, then everyone who joined."""
        project = self.get_object()
        people = [project.owner, *(m.user for m in project.members.select_related("user__profile"))]
        return Response(PersonSerializer(people, many=True).data)

    @extend_schema(request=None, responses={204: None})
    @collaborators.mapping.delete
    def remove_collaborator(self, request, pk=None):
        """Remove someone (`?user=`), or leave, with your own id."""
        project = self.get_object()
        user = serializers.UUIDField().run_validation(request.query_params.get("user"))
        if user != request.user.pk:
            owned(project, request.user)
        elif project.owner_id == user:
            raise ValidationError("Hand the project to someone else before leaving it.")
        member = project.members.filter(user_id=user).select_related("user").first()
        if member is None:
            raise NotFound()
        project.remove(member.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=inline_serializer("Transfer", {"user": serializers.UUIDField()}),
        responses=ProjectSerializer,
        description="Hand the project to one of its collaborators.",
    )
    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        project = owned(self.get_object(), request.user)
        user = serializers.UUIDField().run_validation(request.data.get("user"))
        try:
            project.transfer(project.members.get(user_id=user).user)
        except ProjectMember.DoesNotExist:
            raise ValidationError({"user": "Choose someone in this project."}) from None
        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(
        request=None,
        responses=InviteLinkSerializer,
        description="GET reads the link's token, POST makes a new one (the old one stops "
        "working), DELETE turns joining by link off.",
    )
    @action(detail=True, methods=["get", "post", "delete"], url_path="invite-link")
    def invite_link(self, request, pk=None):
        project = owned(self.get_object(), request.user)
        if project.is_inbox:
            raise NotFound()
        if request.method != "GET":
            project.invite_token = new_invite_token() if request.method == "POST" else ""
            project.save(update_fields=("invite_token", "updated_at"))
        return Response(
            InviteLinkSerializer(
                {"token": project.invite_token or None, "is_full": project.is_full()}
            ).data
        )


class JoinThrottle(ScopedRateThrottle):
    """Joining is rarer than anything else, so a script can't join its way around."""

    scope = "todos_join"

    def get_rate(self):
        return settings.TODOS_PROJECTS_JOIN_RATE


class JoinView(APIView):
    """An invite link: anyone holding it sees the project's name and who shared it;
    a signed-in member joins with POST."""

    throttle_classes = (JoinThrottle,)

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else super().get_permissions()

    def project(self, token):
        project = Project.objects.filter(invite_token=token, is_inbox=False).first()
        if not token or project is None:
            raise NotFound("This invite link doesn't work any more.")
        return project

    @extend_schema(responses=JoinPreviewSerializer)
    def get(self, request, token):
        project = self.project(token)
        project.is_member = (
            request.user.is_authenticated and request.user.pk in project.people_ids()
        )
        project.is_full = project.is_full()
        return Response(JoinPreviewSerializer(project).data)

    @extend_schema(request=None, responses=JoinPreviewSerializer)
    def post(self, request, token):
        project = self.project(token)
        try:
            project.join(request.user)
        except ModelValidationError as error:
            raise ValidationError(error.messages) from None
        return Response(self.preview(project, is_member=True))

    def preview(self, project, is_member):
        return JoinPreviewSerializer(
            {
                "pk": project.pk,
                "name": project.name,
                "owner": project.owner,
                "is_member": is_member,
                "is_full": project.is_full(),
            }
        ).data


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
            pk=self.kwargs["pk"], project__in=Project.objects.visible_to(self.request.user)
        ).first()
        if section is None:
            raise NotFound()
        return section
