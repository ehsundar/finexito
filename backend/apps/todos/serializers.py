from rest_framework import serializers

from apps.todos.models import Label, Project, Section, Task


class CleanedSerializer(serializers.ModelSerializer):
    """Saves through the model's ``full_clean()``, so its rules and limits apply.

    Related fields only offer the caller's own rows; anything else reads as missing.
    """

    def get_fields(self):
        fields = super().get_fields()
        user = self.context["request"].user
        if not user.is_authenticated:  # the schema generator
            return fields
        for field in fields.values():
            field = getattr(field, "child_relation", field)
            if isinstance(field, serializers.PrimaryKeyRelatedField) and not field.read_only:
                field.queryset = field.queryset.model.objects.visible_to(user)
        return fields

    def create(self, validated_data):
        return self.persist(self.Meta.model(), validated_data)

    def update(self, instance, validated_data):
        return self.persist(instance, validated_data)

    def persist(self, instance, data):
        labels = data.pop("labels", None)
        for name, value in data.items():
            setattr(instance, name, value)
        instance.full_clean()
        instance.save()
        if labels is not None:
            instance.labels.set(labels)
        return instance


class ProjectSerializer(CleanedSerializer):
    open_task_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "colour",
            "parent",
            "is_inbox",
            "is_favourite",
            "is_archived",
            "view",
            "sort",
            "order",
            "open_task_count",
            "created_at",
        )
        read_only_fields = ("id", "is_inbox", "order", "created_at")


class SectionSerializer(CleanedSerializer):
    class Meta:
        model = Section
        fields = ("id", "project", "name", "order", "is_archived", "created_at")
        read_only_fields = ("id", "order", "created_at")


class LabelSerializer(CleanedSerializer):
    open_task_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Label
        fields = ("id", "name", "colour", "is_favourite", "order", "open_task_count")
        read_only_fields = ("id", "order")


class TaskSerializer(CleanedSerializer):
    extra = serializers.JSONField(required=False)
    subtask_count = serializers.IntegerField(read_only=True, default=0)
    completed_subtask_count = serializers.IntegerField(read_only=True, default=0)

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
            "completed_at",
            "extra",
            "subtask_count",
            "completed_subtask_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "order", "completed_at", "created_at", "updated_at")


class QuickAddSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=1000)
    # What the view quick add was opened from; tokens in the text win.
    project = serializers.UUIDField(required=False, allow_null=True)
    section = serializers.UUIDField(required=False, allow_null=True)
    parent = serializers.UUIDField(required=False, allow_null=True)
    labels = serializers.ListField(child=serializers.UUIDField(), required=False)


class FilterSerializer(serializers.Serializer):
    slug = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    is_favourite = serializers.BooleanField(read_only=True)
    order = serializers.IntegerField(read_only=True, allow_null=True)
