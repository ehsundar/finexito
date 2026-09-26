from rest_framework.routers import SimpleRouter

from apps.profiles.views import MemberViewSet, ProfileViewSet

router = SimpleRouter()
router.register("profiles", ProfileViewSet, basename="profile")
router.register("members", MemberViewSet, basename="member")

urlpatterns = router.urls
