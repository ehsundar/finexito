from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.programs.models import Program
from apps.programs.permissions import HasProgram
from apps.programs.serializers import ProgramSerializer


class ProgramViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only catalogue of the programs this instance serves."""

    serializer_class = ProgramSerializer
    permission_classes = (AllowAny,)
    queryset = Program.objects.filter(is_active=True).prefetch_related("domains")
    lookup_field = "slug"

    @extend_schema(responses=ProgramSerializer)
    @action(detail=False, methods=["get"], permission_classes=(AllowAny, HasProgram))
    def current(self, request):
        """The program resolved from the header, host or default."""
        return Response(self.get_serializer(request.program).data)
