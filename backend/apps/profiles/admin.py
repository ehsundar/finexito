from django.contrib import admin

from apps.profiles.models import Profile, ProfileSetting


class ProfileSettingInline(admin.TabularInline):
    model = ProfileSetting
    extra = 0


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "program", "role", "status", "enrolled_at")
    list_filter = ("program", "role", "status")
    search_fields = ("display_name", "user__email")
    autocomplete_fields = ("user", "program")
    inlines = (ProfileSettingInline,)


@admin.register(ProfileSetting)
class ProfileSettingAdmin(admin.ModelAdmin):
    list_display = ("profile", "key", "value")
    search_fields = ("key",)
