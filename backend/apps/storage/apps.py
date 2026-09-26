from django.apps import AppConfig


class StorageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.storage"
    label = "storage"

    def ready(self):
        from apps.storage import signals  # noqa: F401
