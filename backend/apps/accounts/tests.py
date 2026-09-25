from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.common.testing import PASSWORD, PlatformTestCase
from apps.profiles.models import Profile

User = get_user_model()


class RegisterTests(PlatformTestCase):
    def test_register_enrols_into_the_current_program(self):
        response = self.client.post(
            reverse("accounts:register"),
            {"email": "New@Example.com", "password": PASSWORD, "display_name": "New"},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["refresh"])
        self.assertEqual(response.data["user"]["email"], "new@example.com")
        self.assertEqual(response.data["profile"]["program"], self.program.slug)
        self.assertTrue(
            Profile.objects.filter(user__email="new@example.com", program=self.program).exists()
        )

    def test_register_without_a_program_creates_the_account_only(self):
        response = self.anonymous_client.post(
            reverse("accounts:register"),
            {"email": "solo@example.com", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data["profile"])

    def test_register_rejects_a_duplicate_email(self):
        response = self.client.post(
            reverse("accounts:register"),
            {"email": self.user.email, "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data["error"]["fields"])

    def test_register_rejects_a_weak_password(self):
        response = self.client.post(
            reverse("accounts:register"),
            {"email": "weak@example.com", "password": "123"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data["error"]["fields"])


class LoginTests(PlatformTestCase):
    def login(self, password=PASSWORD):
        return self.client.post(
            reverse("accounts:login"),
            {"email": self.user.email, "password": password},
            format="json",
        )

    def test_login_returns_a_token_pair(self):
        response = self.login()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["user"]["email"], self.user.email)
        self.assertLessEqual({"access", "refresh", "user"}, set(response.data))

    def test_login_rejects_a_bad_password(self):
        self.assertEqual(self.login(password="wrong-password").status_code, 401)

    def test_access_token_authenticates_me(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.get(reverse("accounts:me"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], self.user.email)

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("accounts:me")).status_code, 401)

    def test_logout_blacklists_the_refresh_token(self):
        tokens = self.login().data
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_X_PROGRAM=self.program.slug
        )

        logout = self.client.post(
            reverse("accounts:logout"), {"refresh": tokens["refresh"]}, format="json"
        )
        refresh = self.client.post(
            reverse("accounts:refresh"), {"refresh": tokens["refresh"]}, format="json"
        )

        self.assertEqual(logout.status_code, 205)
        self.assertEqual(refresh.status_code, 401)


class PasswordChangeTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.authenticate()

    def test_password_change_takes_effect(self):
        response = self.client.post(
            reverse("accounts:password-change"),
            {"current_password": PASSWORD, "new_password": "an0ther-secret-pw"},
            format="json",
        )

        self.assertEqual(response.status_code, 204)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("an0ther-secret-pw"))

    def test_password_change_rejects_a_wrong_current_password(self):
        response = self.client.post(
            reverse("accounts:password-change"),
            {"current_password": "not-it", "new_password": "an0ther-secret-pw"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.data["error"]["fields"])


class UserModelTests(PlatformTestCase):
    def test_email_is_normalised_to_lowercase(self):
        user = User.objects.create_user(email="MiXeD@Example.COM", password=PASSWORD)

        self.assertEqual(user.email, "mixed@example.com")

    def test_superuser_flags(self):
        admin = User.objects.create_superuser(email="admin@example.com", password=PASSWORD)

        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
