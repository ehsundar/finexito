from rest_framework.routers import SimpleRouter

from apps.todos.projects.views import ProjectViewSet, SectionViewSet

router = SimpleRouter()
router.register("todos/projects", ProjectViewSet, basename="todo-project")
router.register("todos/sections", SectionViewSet, basename="todo-section")

urlpatterns = router.urls
