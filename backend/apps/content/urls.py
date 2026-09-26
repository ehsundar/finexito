from rest_framework.routers import SimpleRouter

from apps.content.views import PageViewSet

router = SimpleRouter()
router.register("pages", PageViewSet, basename="page")

urlpatterns = router.urls
