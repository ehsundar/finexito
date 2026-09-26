from rest_framework import serializers

from apps.profiles.models import Profile


class StrictCharField(serializers.CharField):
    """A CharField that rejects numbers and booleans instead of stringifying them."""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    data = serializers.DictField(child=StrictCharField(allow_blank=True), required=False)

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
            "data",
        )
        read_only_fields = ("id", "email", "role", "status", "enrolled_at")


class PublicProfileSerializer(serializers.ModelSerializer):
    """What other members may see."""

    class Meta:
        model = Profile
        fields = ("id", "display_name", "avatar_url", "bio", "role")
        read_only_fields = fields
