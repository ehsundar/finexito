from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.storage import services
from apps.storage.models import StoredObject


class StoredObjectSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = StoredObject
        fields = ("id", "content_type", "visibility", "size", "sha256", "uploaded_at", "url")
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_url(self, obj) -> str | None:
        return services.object_url(obj) if obj.is_ready else None
