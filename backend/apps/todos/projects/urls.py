from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.todos.projects.views import JoinView, ProjectViewSet, SectionViewSet

router = SimpleRouter()
router.register("todos/projects", ProjectViewSet, basename="todo-project")
router.register("todos/sections", SectionViewSet, basename="todo-section")

urlpatterns = [
    path("todos/join/<str:token>/", JoinView.as_view(), name="todo-join"),
    *router.urls,
]
