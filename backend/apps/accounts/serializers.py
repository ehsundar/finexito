from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "is_staff", "date_joined", "last_login")
        read_only_fields = fields


class GoogleStartSerializer(serializers.Serializer):
    """Where to send the browser, and what the frontend keeps until it returns."""

    url = serializers.CharField(read_only=True)
    state = serializers.CharField(read_only=True)
    code_verifier = serializers.CharField(read_only=True)


class GoogleLoginSerializer(serializers.Serializer):
    code = serializers.CharField()
    code_verifier = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)


class TokenRefreshRequestSerializer(serializers.Serializer):
    """The refresh request really only accepts the refresh token.

    SimpleJWT's own serializer also carries the outgoing ``access`` field, which
    leaks into the generated request schema as a required property.
    """

    refresh = serializers.CharField()


class TokenRefreshResponseSerializer(serializers.Serializer):
    """Both tokens come back, because ``ROTATE_REFRESH_TOKENS`` is enabled."""

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
