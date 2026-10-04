from django.contrib import admin

from apps.todos.comments.models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("__str__", "author", "task", "project", "has_attachment", "created_at")
    list_filter = (("attachment", admin.EmptyFieldListFilter),)
    search_fields = ("text", "author__email")
    raw_id_fields = ("task", "project", "author", "attachment")
    readonly_fields = ("edited_at", "created_at", "updated_at")

    @admin.display(description="File", boolean=True)
    def has_attachment(self, obj):
        return obj.attachment_id is not None
