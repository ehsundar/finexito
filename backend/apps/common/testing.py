"""Shared scaffolding for the test suite."""

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from apps.programs.models import Program

User = get_user_model()

PASSWORD = "sup3r-secret-pw"


class PlatformTestCase(APITestCase):
    """A program, a closed program, a user, and a client scoped to the program.

    ``self.client`` sends the X-Program header; ``self.anonymous_client`` is a
    bare client for the cases that need no program to resolve.
    """

    def setUp(self):
        super().setUp()
        self.program = Program.objects.create(
            slug="demo",
            name="Demo",
            enabled_apps=["profiles"],
            default_settings={"theme": "light", "newsletter": False},
        )
        self.closed_program = Program.objects.create(
            slug="closed", name="Closed", allow_self_enrolment=False
        )
        self.user = User.objects.create_user(email="someone@example.com", password=PASSWORD)

        self.anonymous_client = APIClient()
        self.client.credentials(HTTP_X_PROGRAM=self.program.slug)

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)
        return self.client
