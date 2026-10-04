from rest_framework.routers import SimpleRouter

from apps.todos.comments.views import CommentViewSet

router = SimpleRouter()
router.register("todos/comments", CommentViewSet, basename="todo-comment")

urlpatterns = router.urls
