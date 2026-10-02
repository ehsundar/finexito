import json

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from apps.todos.models import FavouriteFilter, Label, Project, Section, Task


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


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("content", "project", "section", "priority", "completed_at")
    list_filter = ("priority", ("completed_at", admin.EmptyFieldListFilter))
    search_fields = ("content",)
    raw_id_fields = ("project", "section", "parent")
    filter_horizontal = ("labels",)
    readonly_fields = ("completed_at", "extra_json", "created_at", "updated_at")
    exclude = ("extra",)

    @admin.display(description="Extra")
    def extra_json(self, obj):
        return format_html("<pre>{}</pre>", json.dumps(obj.extra, indent=2, ensure_ascii=False))


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "task_count", "colour", "is_favourite")
    search_fields = ("name", "owner__email")
    raw_id_fields = ("owner",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(task_count=Count("tasks"))

    @admin.display(description="Tasks", ordering="task_count")
    def task_count(self, obj):
        return obj.task_count


@admin.register(FavouriteFilter)
class FavouriteFilterAdmin(admin.ModelAdmin):
    list_display = ("slug", "owner", "order")
    search_fields = ("slug", "owner__email")
    raw_id_fields = ("owner",)
