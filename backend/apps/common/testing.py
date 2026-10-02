"""Shared scaffolding for the test suite."""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

User = get_user_model()


class PlatformTestCase(APITestCase):
    """A user and an API client."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="someone@example.com")

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)
        return self.client
