from django.contrib import admin

from apps.todos.google.models import Connection


@admin.action(description="Resync the selected connections")
def resync(modeladmin, request, queryset):
    for connection in queryset:
        connection.queue(connection.followed().exclude(due_date=None))
    modeladmin.message_user(request, f"{len(queryset)} connection(s) queued.")


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "last_synced_at", "last_error", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email",)
    raw_id_fields = ("user",)
    readonly_fields = (
        "calendar_id",
        "channel_expires_at",
        "last_synced_at",
        "last_error",
        "created_at",
        "updated_at",
    )
    exclude = ("refresh_token", "channel_id", "channel_token", "channel_resource", "sync_token")
    actions = (resync,)
