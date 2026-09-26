from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import exceptions, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts import services
from apps.accounts.serializers import (
    AuthResponseSerializer,
    DetailSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from apps.common.serializers import ErrorSerializer
from apps.profiles.serializers import ProfileSerializer

User = get_user_model()


class EmailUnavailable(exceptions.APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "We could not send the verification email. Please try again shortly."
    default_code = "email_unavailable"


class RegisterView(GenericAPIView):
    """Create an inactive account and its profile, and email a verification link."""

    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)

    @extend_schema(
        request=RegisterSerializer,
        responses={201: RegisterResponseSerializer, 400: ErrorSerializer, 503: ErrorSerializer},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # One unit: an account whose link never went out could neither sign in
        # nor register again, so a failed send takes the account back out.
        try:
            with transaction.atomic():
                user = serializer.save()
                services.send_verification_email(user)
        except OSError as exc:
            raise EmailUnavailable() from exc

        return Response(
            {
                "detail": "Check your email to activate your account.",
                "user": UserSerializer(user).data,
                "profile": ProfileSerializer(user.profile).data,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(GenericAPIView):
    """Activate an account from its emailed link and sign it in."""

    serializer_class = VerifyEmailSerializer
    permission_classes = (AllowAny,)

    @extend_schema(
        request=VerifyEmailSerializer,
        responses={200: AuthResponseSerializer, 400: ErrorSerializer},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.verify_email(**serializer.validated_data)
        if user is None:
            return Response(
                {
                    "error": {
                        "code": "invalid_link",
                        "message": "This link is invalid or has already been used.",
                        "fields": {},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


class ResendVerificationView(GenericAPIView):
    """Send a fresh link to an unverified account.

    Answers the same whether or not the address has an account, so it cannot be
    used to discover who is registered.
    """

    serializer_class = ResendVerificationSerializer
    permission_classes = (AllowAny,)

    @extend_schema(
        request=ResendVerificationSerializer,
        responses={200: DetailSerializer, 400: ErrorSerializer, 503: ErrorSerializer},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()
        user = User.objects.filter(email=email, is_active=False, is_email_verified=False).first()
        if user:
            try:
                services.send_verification_email(user)
            except OSError as exc:
                raise EmailUnavailable() from exc
        return Response({"detail": "If that account needs verifying, a new link is on its way."})


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
    """The authenticated account."""

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
