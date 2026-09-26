from django.contrib import admin

from apps.messaging.models import EmailMessage, MessageStatus

LEDGER_FIELDS = ("status", "attempts", "next_attempt_at", "sent_at", "last_error")


@admin.action(description="Retry the selected failed messages")
def retry(modeladmin, request, queryset):
    failed = queryset.filter(status=MessageStatus.FAILED)
    for message in failed:
        message.retry()
    modeladmin.message_user(request, f"{len(failed)} message(s) queued again.")


class MessageAdmin(admin.ModelAdmin):
    """The ledger side of every channel's admin."""

    date_hierarchy = "created_at"
    actions = (retry,)
    readonly_fields = (*LEDGER_FIELDS, "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # The ledger is written by code only; the retry action is the way in.
        return False


@admin.register(EmailMessage)
class EmailMessageAdmin(MessageAdmin):
    list_display = ("id", "to", "subject", "status", "attempts", "created_at", "sent_at")
    list_filter = ("status",)
    search_fields = ("id", "to", "subject")
