from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from apps.profiles import services
from apps.profiles.models import Profile, ProfileStatus
from apps.profiles.serializers import (
    EnrolSerializer,
    ProfileSerializer,
    PublicProfileSerializer,
    SettingsSerializer,
)
from apps.programs.permissions import HasProgram


class ProfileViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The caller's profiles, plus their profile in the current program."""

    serializer_class = PublicProfileSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation only
            return Profile.objects.none()
        # Listing shows the caller's own enrolments across every program.
        return (
            Profile.objects.filter(user=self.request.user)
            .select_related("program", "user")
            .prefetch_related("settings")
        )

    def get_serializer_class(self):
        if self.action in {"list", "retrieve"}:
            return ProfileSerializer
        return super().get_serializer_class()

    def _current_profile(self) -> Profile:
        profile = (
            Profile.objects.select_related("program", "user")
            .prefetch_related("settings")
            .filter(user=self.request.user, program=self.request.program)
            .first()
        )
        if profile is None:
            raise PermissionDenied("You are not enrolled in this program.")
        if profile.status == ProfileStatus.SUSPENDED:
            raise PermissionDenied("This profile is suspended.")
        return profile

    @extend_schema(responses=ProfileSerializer)
    @action(
        detail=False,
        methods=["get", "patch"],
        permission_classes=(*viewsets.GenericViewSet.permission_classes, HasProgram),
        url_path="me",
    )
    def me(self, request):
        """Read or update the caller's profile in the current program."""
        profile = self._current_profile()
        if request.method == "GET":
            return Response(ProfileSerializer(profile).data)

        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(request=SettingsSerializer, responses=SettingsSerializer)
    @action(
        detail=False,
        methods=["get", "patch"],
        permission_classes=(*viewsets.GenericViewSet.permission_classes, HasProgram),
        url_path="me/settings",
    )
    def me_settings(self, request):
        """Resolved settings for the current program, or merge overrides in."""
        profile = self._current_profile()
        if request.method == "GET":
            return Response(profile.resolved_settings())

        serializer = SettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(services.update_settings(profile, serializer.validated_data))

    @extend_schema(request=EnrolSerializer, responses=ProfileSerializer)
    @action(detail=False, methods=["post"])
    def enrol(self, request):
        """Join a program -- the one in the body, or the current one."""
        serializer = EnrolSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        program = serializer.validated_data.get("program") or request.program
        if program is None:
            raise PermissionDenied("No program specified or resolved for this request.")
        if not program.allow_self_enrolment:
            raise PermissionDenied("This program does not allow self-enrolment.")

        profile, created = services.enrol(
            request.user, program, display_name=serializer.validated_data.get("display_name", "")
        )
        return Response(
            ProfileSerializer(profile).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ProgramMemberViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Other members of the current program, as they are publicly visible."""

    serializer_class = PublicProfileSerializer
    permission_classes = (*viewsets.GenericViewSet.permission_classes, HasProgram)
    filterset_fields = ("role",)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation only
            return Profile.objects.none()
        return (
            Profile.objects.filter(program=self.request.program, status=ProfileStatus.ACTIVE)
            .select_related("program")
            .order_by("display_name")
        )

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
