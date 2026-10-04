from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.todos.tasks.views import (
    DueDateParseView,
    FilterViewSet,
    LabelViewSet,
    ReminderViewSet,
    TaskViewSet,
)

router = SimpleRouter()
router.register("todos/tasks", TaskViewSet, basename="todo-task")
router.register("todos/labels", LabelViewSet, basename="todo-label")
router.register("todos/filters", FilterViewSet, basename="todo-filter")
router.register("todos/reminders", ReminderViewSet, basename="todo-reminder")

urlpatterns = [
    path("todos/dates/parse/", DueDateParseView.as_view(), name="todo-date-parse"),
    *router.urls,
]
