import json

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from apps.todos.tasks.models import FavouriteFilter, Label, Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("content", "project", "assignee", "priority", "completed_at")
    list_filter = ("priority", ("completed_at", admin.EmptyFieldListFilter))
    search_fields = ("content",)
    raw_id_fields = ("project", "section", "parent", "assignee")
    filter_horizontal = ("labels",)
    readonly_fields = (
        "completed_at",
        "created_by",
        "comment_count",
        "extra_json",
        "created_at",
        "updated_at",
    )
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
