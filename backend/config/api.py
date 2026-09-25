"""Versioned API router.

New platform apps register their routes here; programs then switch them on
individually through ``Program.enabled_apps``.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.profiles.views import ProfileViewSet, ProgramMemberViewSet
from apps.programs.views import ProgramViewSet

router = DefaultRouter()
router.register("programs", ProgramViewSet, basename="program")
router.register("profiles", ProfileViewSet, basename="profile")
router.register("members", ProgramMemberViewSet, basename="member")

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("", include(router.urls)),
]
