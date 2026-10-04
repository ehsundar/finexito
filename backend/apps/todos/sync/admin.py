from django.contrib import admin

from apps.todos.sync.models import SyncOperation, Tombstone


@admin.register(Tombstone)
class TombstoneAdmin(admin.ModelAdmin):
    list_display = ("kind", "object_id", "project_id", "user", "deleted_at")
    list_filter = ("kind",)
    search_fields = ("object_id",)

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SyncOperation)
class SyncOperationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "user__email")

    def has_change_permission(self, request, obj=None):
        return False
