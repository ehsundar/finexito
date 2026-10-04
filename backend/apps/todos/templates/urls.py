from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.todos.templates.views import ProjectExportView, TemplateViewSet

router = SimpleRouter()
router.register("todos/templates", TemplateViewSet, basename="todo-template")

urlpatterns = [
    path(
        "todos/projects/<uuid:pk>/export/", ProjectExportView.as_view(), name="todo-project-export"
    ),
    *router.urls,
]
