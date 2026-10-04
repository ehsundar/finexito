from rest_framework import serializers


class TemplateSerializer(serializers.Serializer):
    """A built-in template (its id is its slug) or one of the member's own."""

    id = serializers.CharField(read_only=True)
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    category = serializers.CharField(read_only=True)
    is_mine = serializers.BooleanField(read_only=True)
    task_count = serializers.IntegerField(read_only=True)
    section_count = serializers.IntegerField(read_only=True)


class SaveTemplateSerializer(serializers.Serializer):
    project = serializers.UUIDField(required=False, help_text="Save this project as a template.")
    file = serializers.FileField(required=False, help_text="Or import a CSV file.")
    name = serializers.CharField(
        max_length=120, required=False, help_text="Default: the project's or file's."
    )
    description = serializers.CharField(max_length=2000, allow_blank=True, required=False)

    def validate(self, attrs):
        if ("project" in attrs) == ("file" in attrs):
            raise serializers.ValidationError("Give a project or a file.")
        return attrs


class ApplyTemplateSerializer(serializers.Serializer):
    project = serializers.UUIDField(
        required=False, allow_null=True, help_text="Add to this project; default a new one."
    )
    name = serializers.CharField(
        max_length=120, required=False, help_text="The new project's name; default the template's."
    )
