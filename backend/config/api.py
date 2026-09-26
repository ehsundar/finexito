"""Versioned API router. New platform apps register their routes here."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.common.views import SiteView
from apps.content.views import PageViewSet
from apps.profiles.views import MemberViewSet, ProfileViewSet

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profile")
router.register("members", MemberViewSet, basename="member")
router.register("pages", PageViewSet, basename="page")

urlpatterns = [
    path("site/", SiteView.as_view(), name="site"),
    path("auth/", include("apps.accounts.urls")),
    path("storage/", include("apps.storage.urls")),
    path("", include(router.urls)),
]
