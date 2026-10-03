from django.contrib import admin

from apps.reminders.models import Reminder, ReminderStatus


@admin.action(description="Fire the selected reminders now")
def fire_now(modeladmin, request, queryset):
    for reminder in queryset:
        reminder.fire()
    modeladmin.message_user(request, f"{len(queryset)} reminder(s) fired.")


@admin.action(description="Retry the selected failed reminders")
def retry(modeladmin, request, queryset):
    failed = queryset.filter(status=ReminderStatus.FAILED)
    for reminder in failed:
        reminder.retry()
    modeladmin.message_user(request, f"{len(failed)} reminder(s) will fire on the next run.")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("user", "content_type", "next_at", "status", "fired_at")
    list_filter = ("status", "content_type")
    search_fields = ("user__email", "object_id")
    raw_id_fields = ("user",)
    readonly_fields = ("next_at", "status", "fired_at", "last_error", "created_at", "updated_at")
    actions = (fire_now, retry)
