from rest_framework import serializers

from apps.profiles.models import Profile
from apps.programs.models import Program


class ProfileSerializer(serializers.ModelSerializer):
    program = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    settings = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "id",
            "program",
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
            "settings",
        )
        read_only_fields = ("id", "program", "email", "role", "status", "enrolled_at")

    def get_settings(self, obj: Profile) -> dict:
        return obj.resolved_settings()


class PublicProfileSerializer(serializers.ModelSerializer):
    """What other members of the same program may see."""

    program = serializers.SlugRelatedField(slug_field="slug", read_only=True)

    class Meta:
        model = Profile
        fields = ("id", "program", "display_name", "avatar_url", "bio", "role")
        read_only_fields = fields


class EnrolSerializer(serializers.Serializer):
    program = serializers.SlugField(required=False)
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=150)

    def validate_program(self, value: str) -> Program:
        program = Program.objects.filter(slug=value, is_active=True).first()
        if program is None:
            raise serializers.ValidationError("No active program with this slug.")
        return program


class SettingsSerializer(serializers.Serializer):
    """Accepts a flat mapping of overrides; ``null`` clears a key."""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                {"settings": ["Expected an object mapping setting keys to values."]}
            )
        invalid = [k for k in data if not isinstance(k, str) or not k.strip()]
        if invalid:
            raise serializers.ValidationError(
                {"settings": ["Setting keys must be non-empty strings."]}
            )
        return data
