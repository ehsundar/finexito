import json
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.db.models import Count, Prefetch, Q
from django.urls import Resolver404, resolve
from django.utils import timezone as tz
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.todos.projects.models import Project, ProjectMember, Section
from apps.todos.projects.serializers import ProjectSerializer, SectionSerializer
from apps.todos.sync.models import SyncOperation, Tombstone
from apps.todos.tasks.models import Label, Task
from apps.todos.tasks.serializers import LabelSerializer, TaskSerializer

# Changes committed a moment after a pull started may carry an earlier time; each
# token reaches back this far, so the next pull still sees them. Rows sent twice
# just overwrite themselves.
OVERLAP = timedelta(seconds=5)


class OperationSerializer(serializers.Serializer):
    id = serializers.UUIDField(help_text="Made by the client; sending it again does nothing.")
    method = serializers.ChoiceField(choices=("POST", "PATCH", "DELETE"))
    path = serializers.CharField(help_text="A todos API path, as the client would call it.")
    body = serializers.JSONField(required=False, default=dict)


class ResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.IntegerField(help_text="As the call would have answered.")
    body = serializers.JSONField(allow_null=True, help_text="Null when sent before.")


class ChangesSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="Send it as `since` next time.")
    full = serializers.BooleanField(help_text="Everything, not changes: replace the local copy.")
    projects = ProjectSerializer(many=True)
    sections = SectionSerializer(many=True)
    tasks = TaskSerializer(many=True)
    labels = LabelSerializer(many=True)
    deleted = inline_serializer(
        "Deleted", {"kind": serializers.CharField(), "id": serializers.UUIDField()}, many=True
    )


class SyncView(APIView):
    """An offline client's two halves: what changed since it last looked, and the
    operations it queued while offline."""

    @extend_schema(
        parameters=[OpenApiParameter("since", str, description="The last token; none for all.")],
        responses=ChangesSerializer,
    )
    def get(self, request):
        user, now = request.user, tz.now()
        keep = timedelta(days=settings.TODOS_SYNC_TOMBSTONE_DAYS)
        Tombstone.objects.filter(deleted_at__lt=now - keep).delete()
        SyncOperation.objects.filter(created_at__lt=now - keep).delete()
        try:
            since = datetime.fromisoformat(request.query_params.get("since") or "")
        except ValueError:
            since = None
        if since and since < now - keep:
            since = None

        projects = Project.objects.visible_to(user)
        sections = Section.objects.filter(project__in=projects)
        tasks = Task.objects.filter(project__in=projects)
        labels = Label.objects.filter(owner=user)
        deleted = Tombstone.objects.none()
        if since:
            # A project joined, or placed anew, since: all of it, as it's new here.
            mine = ProjectMember.objects.filter(user=user)
            fresh = mine.filter(created_at__gt=since).values("project")
            placed = mine.filter(updated_at__gt=since).values("project")
            projects = projects.filter(Q(updated_at__gt=since) | Q(pk__in=fresh) | Q(pk__in=placed))
            sections = sections.filter(Q(updated_at__gt=since) | Q(project__in=fresh))
            tasks = tasks.filter(Q(updated_at__gt=since) | Q(project__in=fresh))
            labels = labels.filter(updated_at__gt=since)
            deleted = Tombstone.objects.filter(deleted_at__gt=since).filter(
                Q(user=user)
                | Q(user=None, project_id__in=Project.objects.visible_to(user).values("pk"))
            )
        context = {"request": request}
        projects = projects.annotate(member_count=Count("members", distinct=True)).prefetch_related(
            Prefetch("members", ProjectMember.objects.filter(user=user), "mine")
        )
        return Response(
            {
                "token": (now - OVERLAP).isoformat(),
                "full": since is None,
                "projects": ProjectSerializer(projects, many=True, context=context).data,
                "sections": SectionSerializer(sections, many=True, context=context).data,
                "tasks": TaskSerializer(
                    tasks.prefetch_related("labels"), many=True, context=context
                ).data,
                "labels": LabelSerializer(labels, many=True, context=context).data,
                "deleted": [{"kind": t.kind, "id": t.object_id} for t in deleted],
            }
        )

    @extend_schema(
        request=inline_serializer("SyncRequest", {"operations": OperationSerializer(many=True)}),
        responses=ResultSerializer(many=True),
        description="Apply queued operations in order, each as its own call to the API, "
        "so every rule and limit applies. A refused one answers its error and the rest go on.",
    )
    def post(self, request):
        ops = OperationSerializer(many=True, data=request.data.get("operations"))
        ops.is_valid(raise_exception=True)
        if len(ops.validated_data) > settings.TODOS_SYNC_MAX_OPERATIONS:
            raise serializers.ValidationError(
                f"Send up to {settings.TODOS_SYNC_MAX_OPERATIONS} operations at a time."
            )
        done = set(
            SyncOperation.objects.filter(
                pk__in=[op["id"] for op in ops.validated_data], user=request.user
            ).values_list("pk", flat=True)
        )
        results = []
        for op in ops.validated_data:
            if op["id"] in done:
                results.append({"id": op["id"], "status": 200, "body": None})
                continue
            status, body = self.replay(request, op)
            SyncOperation.objects.create(id=op["id"], user=request.user, status=status)
            done.add(op["id"])
            results.append({"id": op["id"], "status": status, "body": body})
        return Response(ResultSerializer(results, many=True).data)

    @staticmethod
    def replay(request, op) -> tuple[int, object]:
        """Make the call the client would have made, as the same member."""
        path = urlsplit(op["path"])
        if not path.path.startswith("/api/v1/todos/") or path.path.startswith("/api/v1/todos/sync"):
            return 400, {"error": {"message": "Not a todos call."}}
        try:
            match = resolve(path.path)
        except Resolver404:
            return 404, {"error": {"message": "Not found."}}
        # DRF's request factory builds the request just as a client's would arrive.
        call = APIRequestFactory().generic(
            op["method"],
            op["path"],
            json.dumps(op["body"]),
            content_type="application/json",
        )
        force_authenticate(call, user=request.user)
        response = match.func(call, *match.args, **match.kwargs)
        return response.status_code, getattr(response, "data", None)
