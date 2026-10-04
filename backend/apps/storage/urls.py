from django.urls import path

from apps.storage.views import CompleteView, ObjectView, UploadView

urlpatterns = [
    path("storage/uploads/<uuid:pk>/", UploadView.as_view(), name="storage-upload"),
    path("storage/uploads/<uuid:pk>/complete/", CompleteView.as_view(), name="storage-complete"),
    path("storage/objects/<uuid:pk>/", ObjectView.as_view(), name="storage-object"),
]
