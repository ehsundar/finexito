from django.apps import AppConfig


class TodosTasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.todos.tasks"
    label = "todos_tasks"
