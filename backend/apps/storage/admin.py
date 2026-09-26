from django.contrib import admin
from django.utils.html import format_html

from apps.storage import services
from apps.storage.models import StoredObject


@admin.register(StoredObject)
class StoredObjectAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "content_type", "visibility", "status", "size", "created_at")
    list_filter = ("status", "visibility", "content_type")
    search_fields = ("id", "owner__email", "sha256")
    raw_id_fields = ("owner",)
    readonly_fields = (
        "status",
        "size",
        "sha256",
        "uploaded_at",
        "link",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Link")
    def link(self, obj):
        if not obj.is_ready:
            return "-"
        return format_html(
            '<a href="{0}" target="_blank" rel="noopener">{0}</a>', services.object_url(obj)
        )

    def has_change_permission(self, request, obj=None):
        # The file on disk is immutable; only deleting (which removes it) makes sense.
        return False
