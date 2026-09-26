from django.apps import apps
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.utils.module_loading import module_has_submodule
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def healthz(_request):
    return JsonResponse({"status": "ok"})


# Everything lives under /api/ so the frontend can own the rest of the domain and
# forward a single prefix here. Nothing outside /api/ is served by this project,
# static files included.
urlpatterns = [
    path("api/admin/", admin.site.urls),
    path("api/healthz/", healthz, name="healthz"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

# Each installed app under apps/ that has a urls.py serves it under /api/v1/, so
# removing an app from INSTALLED_APPS removes its routes too.
urlpatterns += [
    path("api/v1/", include(f"{app.name}.urls"))
    for app in apps.get_app_configs()
    if app.name.startswith("apps.") and module_has_submodule(app.module, "urls")
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
