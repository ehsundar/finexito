from rest_framework.routers import SimpleRouter

from apps.todos.views import (
    FilterViewSet,
    LabelViewSet,
    ProjectViewSet,
    SectionViewSet,
    TaskViewSet,
)

router = SimpleRouter()
router.register("todos/projects", ProjectViewSet, basename="todo-project")
router.register("todos/sections", SectionViewSet, basename="todo-section")
router.register("todos/tasks", TaskViewSet, basename="todo-task")
router.register("todos/labels", LabelViewSet, basename="todo-label")
router.register("todos/filters", FilterViewSet, basename="todo-filter")

urlpatterns = router.urls
