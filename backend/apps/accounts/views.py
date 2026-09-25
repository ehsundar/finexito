from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.serializers import (
    AuthResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
    UserSerializer,
)
from apps.common.serializers import ErrorSerializer
from apps.profiles import services as profile_services
from apps.profiles.serializers import ProfileSerializer

User = get_user_model()


class RegisterView(GenericAPIView):
    """Create an account and, if a program is in scope, enrol into it."""

    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)

    @extend_schema(
        request=RegisterSerializer,
        responses={201: RegisterResponseSerializer, 400: ErrorSerializer},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        profile = None
        program = getattr(request, "program", None)
        if program is not None and program.allow_self_enrolment:
            profile, _ = profile_services.enrol(
                user, program, display_name=serializer.validated_data.get("display_name", "")
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "profile": ProfileSerializer(profile).data if profile else None,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    request=LoginSerializer,
    responses={200: AuthResponseSerializer, 401: ErrorSerializer},
)
class LoginView(TokenObtainPairView):
    """Exchange email and password for a JWT pair."""

    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)


class LogoutView(GenericAPIView):
    """Blacklist a refresh token so it can no longer be rotated."""

    serializer_class = LogoutSerializer
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=LogoutSerializer,
        responses={
            205: OpenApiResponse(description="Refresh token blacklisted."),
            400: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response(
                {
                    "error": {
                        "code": "invalid_token",
                        "message": "Token is invalid or expired.",
                        "fields": {},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(GenericAPIView):
    """The authenticated account, independent of any program."""

    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(self.get_serializer(request.user).data)


class PasswordChangeView(GenericAPIView):
    serializer_class = PasswordChangeSerializer
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={
            204: OpenApiResponse(description="Password updated."),
            400: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    request=TokenRefreshRequestSerializer,
    responses={200: TokenRefreshResponseSerializer, 401: ErrorSerializer},
)
class RefreshView(TokenRefreshView):
    """Rotate a refresh token for a fresh pair.

    Subclassed purely so the schema describes the real request and response;
    the behaviour is SimpleJWT's.
    """
