import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from apps.common.testing import PASSWORD, PlatformTestCase
from apps.profiles.models import Profile

User = get_user_model()


class RegisterTests(PlatformTestCase):
    def test_register_creates_an_inactive_account_and_its_profile(self):
        response = self.client.post(
            reverse("accounts:register"),
            {"email": "New@Example.com", "password": PASSWORD, "display_name": "New"},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("access", response.data)
        self.assertEqual(response.data["user"]["email"], "new@example.com")
        self.assertEqual(response.data["profile"]["display_name"], "New")
        self.assertTrue(Profile.objects.filter(user__email="new@example.com").exists())
        self.assertFalse(User.objects.get(email="new@example.com").is_active)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])

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


class EmailVerificationTests(PlatformTestCase):
    email = "new@example.com"

    def register(self):
        self.client.post(
            reverse("accounts:register"),
            {"email": self.email, "password": PASSWORD},
            format="json",
        )

    def link_params(self, message=None):
        body = (message or mail.outbox[-1]).body
        return dict(re.findall(r"[?&](uid|token)=([^&\s]+)", body))

    def verify(self, params):
        return self.client.post(reverse("accounts:verify-email"), params, format="json")

    def login(self):
        return self.client.post(
            reverse("accounts:login"),
            {"email": self.email, "password": PASSWORD},
            format="json",
        )

    def test_email_carries_the_site_name(self):
        with self.settings(SITE_NAME="Acme"):
            self.register()

        self.assertIn("Acme", mail.outbox[0].subject)

    def test_unverified_account_cannot_log_in(self):
        self.register()

        response = self.login()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "email_not_verified")

    def test_unverified_account_with_a_wrong_password_gets_the_generic_error(self):
        self.register()

        response = self.client.post(
            reverse("accounts:login"),
            {"email": self.email, "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_link_activates_the_account_and_signs_it_in(self):
        self.register()

        response = self.verify(self.link_params())

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["user"]["is_email_verified"])
        user = User.objects.get(email=self.email)
        self.assertTrue(user.is_active)
        self.assertEqual(self.login().status_code, 200)

    def test_link_works_only_once(self):
        self.register()
        params = self.link_params()
        self.verify(params)

        response = self.verify(params)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "invalid_link")

    def test_a_tampered_link_is_rejected(self):
        self.register()
        params = self.link_params()

        self.assertEqual(self.verify({**params, "token": "nope"}).status_code, 400)
        self.assertEqual(self.verify({**params, "uid": "garbage"}).status_code, 400)

    def test_resend_sends_a_new_link_to_an_unverified_account(self):
        self.register()

        response = self.client.post(
            reverse("accounts:verify-email-resend"), {"email": self.email}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(self.verify(self.link_params()).status_code, 200)

    def test_resend_answers_the_same_for_unknown_and_active_accounts(self):
        for email in ("nobody@example.com", self.user.email):
            response = self.client.post(
                reverse("accounts:verify-email-resend"), {"email": email}, format="json"
            )
            self.assertEqual(response.status_code, 200)

        self.assertEqual(len(mail.outbox), 0)


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
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

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
