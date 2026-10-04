from django.contrib import admin
from django.db.models import Count

from apps.todos.projects.models import Project, Section


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "task_count", "is_archived", "is_inbox", "created_at")
    list_filter = ("is_archived", "is_inbox")
    search_fields = ("name", "owner__email")
    raw_id_fields = ("owner", "parent")
    readonly_fields = ("is_inbox", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(task_count=Count("tasks"))

    @admin.display(description="Tasks", ordering="task_count")
    def task_count(self, obj):
        return obj.task_count


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "is_archived", "created_at")
    list_filter = ("is_archived",)
    search_fields = ("name", "project__name")
    raw_id_fields = ("project",)
    readonly_fields = ("created_at", "updated_at")
