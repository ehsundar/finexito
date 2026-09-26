from django.contrib import admin

from apps.profiles.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "role", "status", "enrolled_at")
    list_filter = ("role", "status")
    search_fields = ("display_name", "user__email")
    autocomplete_fields = ("user",)
