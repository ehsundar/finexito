from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.profiles import services
from apps.profiles.models import Profile, ProfileStatus
from apps.profiles.serializers import ProfileSerializer, PublicProfileSerializer


class ProfileViewSet(viewsets.GenericViewSet):
    """The caller's own profile."""

    serializer_class = ProfileSerializer

    def _current_profile(self) -> Profile:
        profile = Profile.objects.select_related("user").filter(user=self.request.user).first()
        # Accounts made outside the API (createsuperuser, the admin) have none yet.
        if profile is None:
            profile = services.create_profile(self.request.user)
        if profile.status == ProfileStatus.SUSPENDED:
            raise PermissionDenied("This profile is suspended.")
        return profile

    @extend_schema(responses=ProfileSerializer)
    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """Read or update the caller's profile."""
        profile = self._current_profile()
        if request.method == "GET":
            return Response(ProfileSerializer(profile).data)

        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MemberViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Other members, as they are publicly visible."""

    serializer_class = PublicProfileSerializer
    filterset_fields = ("role",)

    def get_queryset(self):
        return Profile.objects.filter(status=ProfileStatus.ACTIVE).order_by("display_name")

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
