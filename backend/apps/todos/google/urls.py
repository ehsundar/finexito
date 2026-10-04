from django.urls import path

from apps.todos.google.views import CallbackView, ConnectionView, ConnectView, WebhookView

urlpatterns = [
    path("todos/google/", ConnectionView.as_view(), name="todo-google"),
    path("todos/google/connect/", ConnectView.as_view(), name="todo-google-connect"),
    path("todos/google/callback/", CallbackView.as_view(), name="todo-google-callback"),
    path("todos/google/webhook/", WebhookView.as_view(), name="todo-google-webhook"),
]
