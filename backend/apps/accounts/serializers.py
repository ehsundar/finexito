from django.contrib.auth import get_user_model, password_validation
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.profiles.serializers import ProfileSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "is_email_verified", "date_joined", "last_login")
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=150)

    def validate_email(self, value: str) -> str:
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data: dict):
        validated_data.pop("display_name", "")
        return User.objects.create_user(
            email=validated_data["email"], password=validated_data["password"]
        )


class LoginSerializer(TokenObtainPairSerializer):
    """Email/password login returning a JWT pair plus the user payload."""

    username_field = User.USERNAME_FIELD

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_current_password(self, value: str) -> str:
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value, self.context["request"].user)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class AuthResponseSerializer(serializers.Serializer):
    """Documents the login response body, which ``LoginSerializer`` cannot describe.

    ``LoginSerializer`` only declares the write-only credentials it accepts, so
    without this the generated schema claims login returns nothing usable.
    """

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)


class RegisterResponseSerializer(AuthResponseSerializer):
    """As above, plus the profile created when the program allows self-enrolment."""

    profile = ProfileSerializer(read_only=True, allow_null=True)


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
