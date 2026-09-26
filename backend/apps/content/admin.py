from django.contrib import admin

from apps.content.models import Page


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "visibility", "status", "published_at", "updated_at")
    list_filter = ("visibility", "status")
    search_fields = ("title", "slug", "summary")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "slug", "summary", "body")}),
        ("Publishing", {"fields": ("visibility", "status", "published_at")}),
        ("Other", {"fields": ("extra", "created_at", "updated_at"), "classes": ("collapse",)}),
    )
