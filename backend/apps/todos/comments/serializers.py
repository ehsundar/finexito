from rest_framework import serializers

from apps.storage import services
from apps.storage.formats import FORMATS
from apps.storage.models import StoredObject
from apps.todos.comments.models import Comment
from apps.todos.projects.serializers import CleanedSerializer, PersonSerializer


class AttachmentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.SerializerMethodField()
    content_type = serializers.CharField()
    size = serializers.IntegerField()
    url = serializers.SerializerMethodField(help_text="A signed link, good for an hour or so.")

    def get_name(self, obj) -> str:
        return obj.extra.get("name", "")

    def get_url(self, obj) -> str:
        return services.object_url(obj)


class CommentSerializer(CleanedSerializer):
    author = PersonSerializer(read_only=True)
    attachment = AttachmentSerializer(read_only=True, allow_null=True)
    attachment_id = serializers.PrimaryKeyRelatedField(
        source="attachment",
        queryset=StoredObject.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
        help_text="An uploaded file, from `comments/attachments/`; only when posting.",
    )

    class Meta:
        model = Comment
        fields = (
            "id",
            "task",
            "project",
            "author",
            "text",
            "attachment",
            "attachment_id",
            "edited_at",
            "created_at",
        )
        read_only_fields = ("id", "author", "edited_at", "created_at")

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            # What it's on, and what's attached, are fixed once it's posted.
            for name in ("task", "project", "attachment_id"):
                fields[name].read_only = True
        return fields


class AttachmentTicketRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    content_type = serializers.ChoiceField(choices=list(FORMATS))
    size = serializers.IntegerField(min_value=1)


class AttachmentTicketSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    upload_url = serializers.CharField(help_text="PUT the file's raw bytes here.")
