from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.todos.projects.models import Project, ProjectMember, Section

# What a collaborator may change on a shared project: their own place for it,
# and how it's shown. The rest is the owner's.
PLACEMENT_FIELDS = ("parent", "colour", "is_favourite")
SHARED_FIELDS = ("view", "sort")


class CleanedSerializer(serializers.ModelSerializer):
    """Saves through the model's ``full_clean()``, so its rules and limits apply.

    Related fields only offer rows the caller can see; anything else reads as missing.
    A new row may bring its own ``id``, made by a client that was offline, so other
    rows can point at it before the server has seen it.
    """

    def get_fields(self):
        fields = super().get_fields()
        # Only while reading a new row's data: the schema keeps `id` read-only.
        if self.instance is None and hasattr(self, "initial_data") and "id" in fields:
            fields["id"] = serializers.UUIDField(required=False)
        user = self.context["request"].user
        if not user.is_authenticated:  # the schema generator
            return fields
        for field in fields.values():
            field = getattr(field, "child_relation", field)
            if isinstance(field, serializers.PrimaryKeyRelatedField) and not field.read_only:
                rows = field.queryset.model.objects
                if hasattr(rows, "visible_to"):
                    field.queryset = rows.visible_to(user)
        return fields

    def create(self, validated_data):
        model = self.Meta.model
        if "id" in validated_data and model.objects.filter(pk=validated_data["id"]).exists():
            raise serializers.ValidationError({"id": "This id is taken."})
        return self.persist(model(), validated_data)

    def update(self, instance, validated_data):
        return self.persist(instance, validated_data)

    def persist(self, instance, data):
        for name, value in data.items():
            setattr(instance, name, value)
        instance.full_clean()
        instance.save()
        return instance


class PersonSerializer(serializers.Serializer):
    """Someone in a project, as the others in it see them."""

    id = serializers.UUIDField()
    name = serializers.SerializerMethodField()
    email = serializers.EmailField()
    avatar_url = serializers.SerializerMethodField()

    def get_name(self, user) -> str:
        profile = getattr(user, "profile", None)
        return (profile and profile.display_name) or user.email.split("@")[0]

    def get_avatar_url(self, user) -> str:
        profile = getattr(user, "profile", None)
        return profile.avatar_url if profile else ""


class ProjectSerializer(CleanedSerializer):
    """For a collaborator, ``parent``, ``order``, ``colour`` and ``is_favourite``
    are their own place for the project."""

    open_task_count = serializers.IntegerField(read_only=True, default=0)
    is_owner = serializers.SerializerMethodField()
    is_shared = serializers.SerializerMethodField()

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
            "is_owner",
            "is_shared",
            "open_task_count",
            "created_at",
        )
        read_only_fields = ("id", "is_inbox", "order", "created_at")

    def caller(self):
        return self.context["request"].user

    def membership(self, project) -> ProjectMember | None:
        if project.owner_id == self.caller().pk:
            return None
        mine = getattr(project, "mine", None)
        if mine is None:
            mine = list(project.members.filter(user=self.caller()))
        return mine[0] if mine else None

    def get_is_owner(self, project) -> bool:
        return project.owner_id == self.caller().pk

    def get_is_shared(self, project) -> bool:
        count = getattr(project, "member_count", None)
        return bool(count if count is not None else project.members.exists())

    def to_representation(self, project):
        data = super().to_representation(project)
        if member := self.membership(project):
            data.update(
                parent=member.parent_id and str(member.parent_id),
                order=member.order,
                colour=member.colour,
                is_favourite=member.is_favourite,
            )
        return data

    def persist(self, project, data):
        member = None if project._state.adding else self.membership(project)
        if member is None:
            return super().persist(project, data)
        if set(data) - {*PLACEMENT_FIELDS, *SHARED_FIELDS}:
            raise PermissionDenied("Only the project's owner can change that.")
        for name in PLACEMENT_FIELDS:
            if name in data:
                setattr(member, name, data.pop(name))
        member.full_clean()
        member.save()
        return super().persist(project, data) if data else project


class SectionSerializer(CleanedSerializer):
    class Meta:
        model = Section
        fields = ("id", "project", "name", "order", "is_archived", "created_at")
        read_only_fields = ("id", "order", "created_at")

    def validate_project(self, project):
        moving_out = self.instance and self.instance.project_id != project.pk
        if moving_out and self.instance.project.owner_id != self.context["request"].user.pk:
            raise serializers.ValidationError("Only the project's owner can move sections out.")
        return project


class InviteLinkSerializer(serializers.Serializer):
    token = serializers.CharField(allow_null=True, help_text="Null when joining is off.")
    is_full = serializers.BooleanField()


class JoinPreviewSerializer(serializers.Serializer):
    project = serializers.UUIDField(source="pk")
    name = serializers.CharField()
    invited_by = PersonSerializer(source="owner")
    is_member = serializers.BooleanField()
    is_full = serializers.BooleanField()
