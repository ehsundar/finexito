from rest_framework import serializers

from apps.todos.projects.models import Project, Section


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
