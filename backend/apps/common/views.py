from django.conf import settings
from django.http import JsonResponse


def manifest(request):
    """
    The web app manifest, so a phone can install the site; it opens on the home
    page. Also where the frontend reads what this deployment is called.
    """
    return JsonResponse(
        {
            "name": settings.SITE_NAME,
            "short_name": settings.SITE_NAME,
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "icons": [
                {"src": "/brand/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/brand/icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        },
        content_type="application/manifest+json",
    )
