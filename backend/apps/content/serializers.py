from rest_framework import serializers

from apps.content.models import Page


class PageSummarySerializer(serializers.ModelSerializer):
    """What a listing needs: everything but the body."""

    class Meta:
        model = Page
        fields = ("id", "slug", "title", "summary", "visibility", "published_at", "updated_at")
        read_only_fields = fields


class PageSerializer(PageSummarySerializer):
    class Meta(PageSummarySerializer.Meta):
        fields = (*PageSummarySerializer.Meta.fields, "body")
        read_only_fields = fields
