from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"
    label = "common"

    def ready(self):
        from django.conf import settings
        from django.contrib import admin

        admin.site.site_header = f"{settings.SITE_NAME} administration"
        admin.site.site_title = settings.SITE_NAME
