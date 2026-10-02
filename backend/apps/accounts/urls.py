from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("auth/google/start/", views.GoogleStartView.as_view(), name="google-start"),
    path("auth/google/", views.GoogleLoginView.as_view(), name="google"),
    path("auth/refresh/", views.RefreshView.as_view(), name="refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="verify"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
]
