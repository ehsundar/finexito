from django.apps import AppConfig


class TodosSyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.todos.sync"
    label = "todos_sync"
