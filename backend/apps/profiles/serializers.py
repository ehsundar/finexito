from rest_framework import serializers

from apps.common.serializers import ExtraField
from apps.profiles.models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    extra = ExtraField()

    class Meta:
        model = Profile
        fields = (
            "id",
            "email",
            "display_name",
            "avatar_url",
            "bio",
            "locale",
            "timezone",
            "role",
            "status",
            "enrolled_at",
            "extra",
        )
        read_only_fields = ("id", "email", "role", "status", "enrolled_at")


class PublicProfileSerializer(serializers.ModelSerializer):
    """What other members may see."""

    class Meta:
        model = Profile
        fields = ("id", "display_name", "avatar_url", "bio", "role")
        read_only_fields = fields
