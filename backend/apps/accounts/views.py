import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import exceptions, status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.serializers import (
    AuthResponseSerializer,
    GoogleLoginSerializer,
    GoogleStartSerializer,
    LogoutSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
    UserSerializer,
)
from apps.common.serializers import ErrorSerializer
from apps.profiles import services as profile_services

User = get_user_model()

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


def google_redirect_uri() -> str:
    return f"{settings.PUBLIC_ORIGIN}/auth/google/callback"


class GoogleSignInFailed(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Google sign-in did not complete. Please try again."
    default_code = "google_sign_in_failed"


class AccountDisabled(exceptions.PermissionDenied):
    default_detail = "This account has been disabled."
    default_code = "account_disabled"


class GoogleStartView(GenericAPIView):
    """Begin Google sign-in: the authorisation URL, with its state and PKCE verifier.

    The frontend keeps `state` and `code_verifier` in sessionStorage, sends
    the browser to `url`, and hands both back to `auth/google/` on return.
    """

    serializer_class = GoogleStartSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(request=None, responses=GoogleStartSerializer)
    def post(self, request):
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        query = urllib.parse.urlencode(
            {
                "client_id": settings.ACCOUNTS_GOOGLE_CLIENT_ID,
                "redirect_uri": google_redirect_uri(),
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return Response(
            {"url": f"{GOOGLE_AUTHORIZE_URL}?{query}", "state": state, "code_verifier": verifier}
        )


class GoogleLoginView(GenericAPIView):
    """Finish Google sign-in: exchange the code, find or create the account, sign it in."""

    serializer_class = GoogleLoginSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        request=GoogleLoginSerializer,
        responses={200: AuthResponseSerializer, 400: ErrorSerializer, 403: ErrorSerializer},
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        claims = self.exchange(**serializer.validated_data)

        with transaction.atomic():
            user = self.find_or_create(claims)
        if not user.is_active:
            raise AccountDisabled()

        update_last_login(None, user)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )

    @staticmethod
    def exchange(code: str, code_verifier: str) -> dict:
        """Trade the code for Google's ID token and return its checked claims."""
        body = urllib.parse.urlencode(
            {
                "code": code,
                "code_verifier": code_verifier,
                "client_id": settings.ACCOUNTS_GOOGLE_CLIENT_ID,
                "client_secret": settings.ACCOUNTS_GOOGLE_CLIENT_SECRET,
                "redirect_uri": google_redirect_uri(),
                "grant_type": "authorization_code",
            }
        ).encode()
        try:
            with urllib.request.urlopen(GOOGLE_TOKEN_URL, data=body, timeout=10) as response:
                id_token = json.load(response)["id_token"]
        except (urllib.error.URLError, KeyError, ValueError) as exc:
            raise GoogleSignInFailed() from exc

        # The token came straight from Google over TLS, so its signature needs no
        # checking (Google's OpenID Connect guide says as much); the claims do.
        try:
            payload = id_token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        except (IndexError, ValueError) as exc:
            raise GoogleSignInFailed() from exc
        if (
            claims.get("aud") != settings.ACCOUNTS_GOOGLE_CLIENT_ID
            or claims.get("iss") not in GOOGLE_ISSUERS
            or claims.get("exp", 0) < time.time()
            or not claims.get("email_verified")
            or not claims.get("sub")
            or not claims.get("email")
        ):
            raise GoogleSignInFailed()
        return claims

    @staticmethod
    def find_or_create(claims: dict):
        email = claims["email"].lower()
        user = User.objects.filter(google_sub=claims["sub"]).first()
        if user:
            if user.email != email:
                user.email = email
                user.save(update_fields=["email"])
            return user

        # An account made without Google (`login_as` in development) is linked
        # on first sign-in. Safe because Google has verified the address.
        user = User.objects.filter(email=email).first()
        if user:
            user.google_sub = claims["sub"]
            user.save(update_fields=["google_sub"])
            return user

        user = User.objects.create_user(email=email, google_sub=claims["sub"])
        profile_services.create_profile(user, display_name=claims.get("name", ""))
        return user


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


@extend_schema(
    request=TokenRefreshRequestSerializer,
    responses={200: TokenRefreshResponseSerializer, 401: ErrorSerializer},
)
class RefreshView(TokenRefreshView):
    """Rotate a refresh token for a fresh pair.

    Subclassed purely so the schema describes the real request and response;
    the behaviour is SimpleJWT's.
    """
