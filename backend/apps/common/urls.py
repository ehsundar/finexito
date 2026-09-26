from django.urls import path

from apps.common.views import SiteView

urlpatterns = [
    path("site/", SiteView.as_view(), name="site"),
]
