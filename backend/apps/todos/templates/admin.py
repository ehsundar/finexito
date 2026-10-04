from django.contrib import admin

from apps.todos.templates.models import Template


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__email")
    raw_id_fields = ("owner",)
