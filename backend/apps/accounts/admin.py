from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-date_joined",)
    list_display = ("email", "is_active", "is_staff", "is_email_verified", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser", "is_email_verified")
    search_fields = ("email",)
    readonly_fields = ("date_joined", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Status"), {"fields": ("is_active", "is_email_verified")}),
        (_("Permissions"), {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
