from django.urls import path

from apps.common.views import manifest

urlpatterns = [
    path("manifest.webmanifest", manifest, name="manifest"),
]
