from django.conf import settings
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone as tz
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.storage import services
from apps.storage.models import ObjectVisibility, StoredObject
from apps.todos.comments.models import ATTACHMENT_PURPOSE, Comment
from apps.todos.comments.serializers import (
    AttachmentTicketRequestSerializer,
    AttachmentTicketSerializer,
    CommentSerializer,
)
from apps.todos.projects.views import TodosViewSet, WriteThrottle


class CommentThrottle(ScopedRateThrottle):
    """Caps new comments and uploads per member at TODOS_COMMENTS_RATE."""

    scope = "todos_comments"

    def get_rate(self):
        return settings.TODOS_COMMENTS_RATE

    def allow_request(self, request, view):
        if request.method != "POST":
            return True
        return super().allow_request(request, view)


@extend_schema(
    parameters=[
        OpenApiParameter("task", str, description="The task's comments."),
        OpenApiParameter("project", str, description="The project's own comments."),
    ]
)
class CommentViewSet(TodosViewSet):
    """Oldest first. The author edits or deletes their own; the project's owner
    deletes any."""

    serializer_class = CommentSerializer
    throttle_classes = (WriteThrottle, CommentThrottle)

    def rows(self):
        comments = Comment.objects.visible_to(self.request.user).select_related(
            "author__profile", "attachment", "task__project", "project"
        )
        if self.action == "list":
            params = self.request.query_params
            if task := params.get("task"):
                comments = comments.filter(task=task)
            elif project := params.get("project"):
                comments = comments.filter(project=project)
            else:
                raise ValidationError("Ask for a task's comments or a project's.")
        return comments

    def perform_create(self, serializer):
        serializer.save(author=self.request.user).notify()

    def perform_update(self, serializer):
        if serializer.instance.author_id != self.request.user.pk:
            raise PermissionDenied("Only its author can edit a comment.")
        serializer.save(edited_at=tz.now())

    def perform_destroy(self, comment):
        user = self.request.user
        if user.pk not in (comment.author_id, comment.where.owner_id):
            raise PermissionDenied("Only its author or the project's owner can delete it.")
        comment.delete()

    # Comments keep the order they were written in.
    reorder = None

    @extend_schema(
        request=AttachmentTicketRequestSerializer,
        responses={201: AttachmentTicketSerializer},
        description="Open an upload ticket for a comment's file: PUT the file to "
        "`upload_url`, then post the comment with its `id` as `attachment_id`.",
    )
    @action(detail=False, methods=["post"])
    def attachments(self, request):
        ticket = AttachmentTicketRequestSerializer(data=request.data)
        ticket.is_valid(raise_exception=True)
        size = ticket.validated_data["size"]
        if size > settings.TODOS_COMMENTS_MAX_ATTACHMENT_BYTES:
            limit = settings.TODOS_COMMENTS_MAX_ATTACHMENT_BYTES // 1024**2
            raise ValidationError({"size": f"Attach files up to {limit} MB."})
        used = StoredObject.objects.filter(
            owner=request.user, extra__purpose=ATTACHMENT_PURPOSE
        ).aggregate(used=Sum(Coalesce("size", "max_size")))["used"]
        if (used or 0) + size > settings.TODOS_COMMENTS_MAX_STORAGE_BYTES:
            raise ValidationError({"size": "You've used all the space for attachments."})
        obj = services.create_upload(
            request.user,
            content_type=ticket.validated_data["content_type"],
            max_size=size,
            visibility=ObjectVisibility.PRIVATE,
            purpose=ATTACHMENT_PURPOSE,
            name=ticket.validated_data["name"],
        )
        return Response(
            AttachmentTicketSerializer({"id": obj.pk, "upload_url": services.upload_url(obj)}).data,
            status=status.HTTP_201_CREATED,
        )
