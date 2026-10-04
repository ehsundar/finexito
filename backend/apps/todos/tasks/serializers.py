from datetime import datetime

from django.utils import timezone as tz
from rest_framework import serializers

from apps.reminders.models import Reminder, zone
from apps.todos.projects.serializers import CleanedSerializer
from apps.todos.tasks.dates import Due
from apps.todos.tasks.models import Label, Task, member_today, member_zone


class LabelSerializer(CleanedSerializer):
    open_task_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Label
        fields = ("id", "name", "colour", "is_favourite", "order", "open_task_count")
        read_only_fields = ("id", "order")


class TaskSerializer(CleanedSerializer):
    """Due dates and times read and write in the caller's time zone.

    Writing ``due_string`` parses it and sets the rest; writing ``due_date`` or
    ``due_time`` sets those, keeping whichever isn't sent, and a recurring task
    keeps recurring.
    """

    extra = serializers.JSONField(required=False)
    subtask_count = serializers.IntegerField(read_only=True, default=0)
    completed_subtask_count = serializers.IntegerField(read_only=True, default=0)
    due_time = serializers.TimeField(required=False, allow_null=True)
    due_string = serializers.CharField(required=False, allow_blank=True, max_length=200)
    is_recurring = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = (
            "id",
            "project",
            "section",
            "parent",
            "order",
            "content",
            "description",
            "priority",
            "labels",
            "assignee",
            "created_by",
            "comment_count",
            "completed_at",
            "due_date",
            "due_time",
            "due_string",
            "is_recurring",
            "due_from_completion",
            "is_overdue",
            "extra",
            "subtask_count",
            "completed_subtask_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "order",
            "created_by",
            "comment_count",
            "completed_at",
            "due_from_completion",
            "created_at",
            "updated_at",
        )

    def caller(self):
        return self.context["request"].user

    def validate_project(self, project):
        moving_out = self.instance and self.instance.project_id != project.pk
        if moving_out and self.instance.project.owner_id != self.caller().pk:
            raise serializers.ValidationError("Only the project's owner can move tasks out.")
        return project

    def persist(self, task, data):
        """Labels are the caller's: setting them leaves everyone else's alone."""
        labels = data.pop("labels", None)
        task = super().persist(task, data)
        if labels is not None:
            theirs = task.labels.exclude(owner=self.caller())
            task.labels.set([*theirs, *labels])
        return task

    def zone(self):
        return zone(member_zone(self.context["request"].user))

    def get_is_recurring(self, task) -> bool:
        return bool(task.due_rule)

    def get_is_overdue(self, task) -> bool:
        if task.completed_at or not task.due_date:
            return False
        if task.due_at:
            return task.due_at < tz.now()
        return task.due_date < member_today(self.context["request"].user)

    def to_representation(self, task):
        data = super().to_representation(task)
        data["labels"] = [
            str(label.pk) for label in task.labels.all() if label.owner_id == self.caller().pk
        ]
        if task.due_at:
            local = task.due_at.astimezone(self.zone())
            data["due_date"], data["due_time"] = local.date().isoformat(), local.strftime("%H:%M")
        else:
            data["due_time"] = None
        return data

    def validate(self, attrs):
        task = self.instance
        if "due_string" in attrs:
            text = attrs["due_string"].strip()
            try:
                due = Due.parse(text, member_today(self.context["request"].user)) if text else Due()
            except ValueError:
                raise serializers.ValidationError(
                    {"due_string": "Couldn't understand that date."}
                ) from None
            day, at = due.date, due.time
            attrs.update(
                due_string=due.string, due_rule=due.rule, due_from_completion=due.from_completion
            )
        elif "due_date" in attrs or "due_time" in attrs:
            local = task.due_at.astimezone(self.zone()) if task and task.due_at else None
            day = attrs.get("due_date", task.due_date if task else None)
            at = attrs["due_time"] if "due_time" in attrs else local and local.time()
            if not (task and task.due_rule):
                attrs["due_string"] = ""
        else:
            return attrs
        attrs.pop("due_time", None)
        attrs["due_date"] = day
        attrs["due_at"] = datetime.combine(day, at, tzinfo=self.zone()) if day and at else None
        return attrs


class ReminderSerializer(serializers.ModelSerializer):
    """One of a task's reminders: ``minutes_before`` its due time, or ``at`` a moment."""

    minutes_before = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=60 * 24 * 28
    )
    at = serializers.DateTimeField(source="start_at", required=False)

    class Meta:
        model = Reminder
        fields = ("id", "minutes_before", "at", "next_at", "status")
        read_only_fields = ("id", "next_at", "status")

    def to_representation(self, reminder):
        data = super().to_representation(reminder)
        before = reminder.extra.get("minutes_before")
        data["minutes_before"] = int(before) if before is not None else None
        return data

    def validate(self, attrs):
        if (attrs.get("minutes_before") is None) == ("start_at" not in attrs):
            raise serializers.ValidationError("Give either minutes_before or at.")
        return attrs


class DueSerializer(serializers.Serializer):
    date = serializers.DateField(allow_null=True)
    time = serializers.TimeField(allow_null=True, format="%H:%M")
    string = serializers.CharField()
    is_recurring = serializers.SerializerMethodField()
    from_completion = serializers.BooleanField()

    def get_is_recurring(self, due) -> bool:
        return bool(due.rule)


class DueParseSerializer(serializers.Serializer):
    due = DueSerializer(allow_null=True, default=None)
    match = serializers.ListField(
        child=serializers.IntegerField(),
        allow_null=True,
        default=None,
        help_text="Where the phrase starts and ends in the text.",
    )
    content = serializers.CharField(allow_blank=True, help_text="The text without the phrase.")


class FilterSerializer(serializers.Serializer):
    slug = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    is_favourite = serializers.BooleanField(read_only=True)
    order = serializers.IntegerField(read_only=True, allow_null=True)
