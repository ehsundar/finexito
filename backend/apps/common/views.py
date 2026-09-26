from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class SiteSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)


class SiteView(APIView):
    """What this deployment is called, so the frontend never hard-codes it."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(responses=SiteSerializer)
    def get(self, request):
        return Response({"name": settings.SITE_NAME})
