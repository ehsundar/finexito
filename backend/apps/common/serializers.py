from rest_framework import serializers


class ReadOnlyModelSerializer(serializers.ModelSerializer):
    """Convenience base for representation-only payloads."""

    def get_fields(self):
        fields = super().get_fields()
        for field in fields.values():
            field.read_only = True
        return fields


class ErrorDetailSerializer(serializers.Serializer):
    """The inner payload of the envelope built by ``common.exceptions``."""

    code = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    fields = serializers.DictField(read_only=True)


class ErrorSerializer(serializers.Serializer):
    """Documents the single error envelope every failing response uses."""

    error = ErrorDetailSerializer(read_only=True)
