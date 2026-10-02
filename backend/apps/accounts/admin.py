from django.conf import settings
from django.contrib import admin
from django.contrib.auth import login
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.accounts.models import User

# The frontend's session cookie (frontend/src/lib/auth/session.ts). It is set on
# the same host, so Django receives it too, in production and on localhost.
ACCESS_COOKIE = "access_token"


def admin_login(request, extra_context=None):
    """Nobody has a password: the admin signs in whoever the frontend has signed in.

    A staff member with a live session gets a Django session and goes on to the
    admin; anyone else is sent to sign in on the frontend first.
    """
    auth = JWTAuthentication()
    try:
        user = auth.get_user(auth.get_validated_token(request.COOKIES.get(ACCESS_COOKIE, "")))
    except (InvalidToken, TokenError):
        user = None

    if user is None or not user.is_active or not user.is_staff:
        return redirect(f"{settings.PUBLIC_ORIGIN}/auth/refresh?next={request.path}")

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    next_url = request.GET.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = "admin:index"
    return redirect(next_url)


admin.site.login = admin_login


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-date_joined",)
    list_display = ("email", "is_active", "is_staff", "is_superuser", "date_joined", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email",)
    readonly_fields = ("email", "google_sub", "date_joined", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "google_sub")}),
        (_("Status"), {"fields": ("is_active",)}),
        (_("Permissions"), {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Dates"), {"fields": ("last_login", "date_joined")}),
    )

    def has_add_permission(self, request):
        # Accounts come from Google sign-in, not from here.
        return False
