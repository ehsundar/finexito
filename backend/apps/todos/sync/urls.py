from django.urls import path

from apps.todos.sync.views import SyncView

urlpatterns = [path("todos/sync/", SyncView.as_view(), name="todo-sync")]
