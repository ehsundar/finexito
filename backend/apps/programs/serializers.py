from rest_framework import serializers

from apps.programs.models import Program, ProgramDomain


class ProgramDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramDomain
        fields = ("host", "is_primary")


class ProgramSerializer(serializers.ModelSerializer):
    domains = ProgramDomainSerializer(many=True, read_only=True)

    class Meta:
        model = Program
        fields = (
            "id",
            "slug",
            "name",
            "description",
            "enabled_apps",
            "allow_self_enrolment",
            "default_settings",
            "domains",
        )
        read_only_fields = fields
