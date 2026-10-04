import urllib.error

from django.core import signing
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.todos.google.models import Connection, pull_changes
from apps.todos.projects.models import Project
from apps.todos.projects.views import WriteThrottle
from apps.todos.tasks.models import Task

STATE_SALT = "todos.google.connect"


class ConnectionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("none", "connected", "disconnected"))
    projects = serializers.ListField(
        child=serializers.UUIDField(),
        allow_null=True,
        help_text="The member's projects the calendar shows; null for all.",
    )
    last_synced_at = serializers.DateTimeField(allow_null=True)
    last_error = serializers.CharField(allow_blank=True)


def describe(connection: Connection | None) -> dict:
    if connection is None:
        return {"status": "none", "projects": None, "last_synced_at": None, "last_error": ""}
    return {
        "status": connection.status,
        "projects": connection.projects,
        "last_synced_at": connection.last_synced_at,
        "last_error": connection.last_error,
    }


class ConnectionView(APIView):
    """The member's Google Calendar: whether it's connected, which projects it shows,
    and disconnecting it."""

    throttle_classes = (WriteThrottle,)

    def connection(self):
        return Connection.objects.filter(user=self.request.user).first()

    @extend_schema(responses=ConnectionSerializer)
    def get(self, request):
        return Response(ConnectionSerializer(describe(self.connection())).data)

    @extend_schema(
        request=inline_serializer(
            "ConnectionProjects",
            {"projects": serializers.ListField(child=serializers.UUIDField(), allow_null=True)},
        ),
        responses=ConnectionSerializer,
    )
    def patch(self, request):
        connection = self.connection()
        if connection is None:
            raise ValidationError("Connect Google Calendar first.")
        projects = serializers.ListField(
            child=serializers.UUIDField(), allow_null=True
        ).run_validation(request.data.get("projects"))
        own = Project.objects.filter(owner=request.user)
        if projects is not None:
            projects = [str(pk) for pk in own.filter(pk__in=projects).values_list("pk", flat=True)]
        connection.projects = projects
        connection.save(update_fields=("projects", "updated_at"))
        # Every dated task they might have followed, to add or remove its event.
        connection.queue(
            Task.objects.filter(project__in=Project.objects.visible_to(request.user)).exclude(
                due_date=None
            )
        )
        return Response(ConnectionSerializer(describe(connection)).data)

    @extend_schema(responses={204: None})
    def delete(self, request):
        if connection := self.connection():
            connection.disconnect()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConnectView(APIView):
    """Start consent: Google's URL to send the browser to."""

    @extend_schema(responses=inline_serializer("GoogleConsent", {"url": serializers.URLField()}))
    def get(self, request):
        state = signing.dumps(str(request.user.pk), salt=STATE_SALT)
        return Response({"url": Connection.consent_url(request.user, state)})


class CallbackView(APIView):
    """Finish consent, with the `code` and `state` Google sent back to the page."""

    @extend_schema(
        parameters=[OpenApiParameter("code", str, required=True), OpenApiParameter("state", str)],
        responses=ConnectionSerializer,
    )
    def get(self, request):
        try:
            user = signing.loads(
                request.query_params.get("state", ""), salt=STATE_SALT, max_age=600
            )
        except signing.BadSignature:
            raise ValidationError("Start connecting again.") from None
        if user != str(request.user.pk) or not request.query_params.get("code"):
            raise ValidationError("Start connecting again.")
        try:
            connection = Connection.connect(request.user, request.query_params["code"])
        except (urllib.error.URLError, KeyError, ValueError):
            raise ValidationError("Google didn't let the calendar connect. Try again.") from None
        return Response(ConnectionSerializer(describe(connection)).data)


@extend_schema(exclude=True)
class WebhookView(APIView):
    """Google's notice that the calendar changed, checked by the channel's token."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request):
        connection = Connection.objects.filter(
            channel_id=request.headers.get("X-Goog-Channel-ID", "") or None,
            channel_token=request.headers.get("X-Goog-Channel-Token", "") or None,
        ).first()
        if connection is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if request.headers.get("X-Goog-Resource-State") != "sync":
            pull_changes.enqueue(str(connection.pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
