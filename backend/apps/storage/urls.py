from django.urls import path

from apps.storage.views import ObjectView, UploadView

urlpatterns = [
    path("uploads/<uuid:pk>/", UploadView.as_view(), name="storage-upload"),
    path("objects/<uuid:pk>/", ObjectView.as_view(), name="storage-object"),
]
