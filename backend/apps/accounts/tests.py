import base64
import io
import json
import time
import urllib.parse
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.testing import PlatformTestCase
from apps.profiles.models import Profile

User = get_user_model()

CLIENT_ID = "client-id.apps.googleusercontent.com"


def google_response(**overrides):
    """What Google's token endpoint answers, with an ID token carrying these claims."""
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "exp": time.time() + 3600,
        "sub": "google-123",
        "email": "New.Person@example.com",
        "email_verified": True,
        "name": "New Person",
        **overrides,
    }
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return io.BytesIO(json.dumps({"id_token": f"header.{payload}.signature"}).encode())


@override_settings(ACCOUNTS_GOOGLE_CLIENT_ID=CLIENT_ID, ACCOUNTS_GOOGLE_CLIENT_SECRET="secret")
class GoogleSignInTests(PlatformTestCase):
    def sign_in(self, **claims):
        with mock.patch("urllib.request.urlopen", return_value=google_response(**claims)) as post:
            response = self.client.post(
                reverse("accounts:google"), {"code": "c", "code_verifier": "v"}, format="json"
            )
        self.token_request = urllib.parse.parse_qs(post.call_args.kwargs["data"].decode())
        return response

    def test_start_builds_the_authorisation_url(self):
        data = self.client.post(reverse("accounts:google-start")).data
        query = urllib.parse.parse_qs(urllib.parse.urlparse(data["url"]).query)

        self.assertEqual(query["client_id"], [CLIENT_ID])
        self.assertEqual(query["redirect_uri"], ["http://localhost:3000/auth/google/callback"])
        self.assertEqual(query["state"], [data["state"]])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertTrue(data["code_verifier"])

    def test_first_sign_in_creates_the_account_and_its_profile(self):
        response = self.sign_in()

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="new.person@example.com")
        self.assertEqual(user.google_sub, "google-123")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(Profile.objects.get(user=user).display_name, "New Person")
        self.assertEqual(response.data["user"]["email"], "new.person@example.com")
        self.assertIn("access", response.data)
        self.assertEqual(self.token_request["code_verifier"], ["v"])

    def test_a_returning_account_is_found_by_google_id_even_with_a_new_email(self):
        self.sign_in()
        self.sign_in(email="renamed@example.com")

        self.assertEqual(User.objects.get(google_sub="google-123").email, "renamed@example.com")

    def test_an_account_made_without_google_is_linked_by_email(self):
        self.sign_in(email=self.user.email, sub="google-999")

        self.user.refresh_from_db()
        self.assertEqual(self.user.google_sub, "google-999")

    def test_an_unverified_google_email_is_refused(self):
        response = self.sign_in(email_verified=False)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "google_sign_in_failed")
        self.assertFalse(User.objects.filter(email="new.person@example.com").exists())

    def test_a_token_for_another_client_is_refused(self):
        self.assertEqual(self.sign_in(aud="someone-else").status_code, 400)

    def test_a_disabled_account_cannot_sign_in(self):
        self.user.is_active = False
        self.user.save()

        response = self.sign_in(email=self.user.email)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "account_disabled")


class SessionTests(PlatformTestCase):
    def tokens(self):
        refresh = RefreshToken.for_user(self.user)
        return str(refresh.access_token), str(refresh)

    def test_access_token_authenticates_me(self):
        access, _ = self.tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.get(reverse("accounts:me"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], self.user.email)

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("accounts:me")).status_code, 401)

    def test_logout_blacklists_the_refresh_token(self):
        access, refresh = self.tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        logout = self.client.post(reverse("accounts:logout"), {"refresh": refresh}, format="json")
        rotate = self.client.post(reverse("accounts:refresh"), {"refresh": refresh}, format="json")

        self.assertEqual(logout.status_code, 205)
        self.assertEqual(rotate.status_code, 401)


class AdminLoginTests(PlatformTestCase):
    def test_a_staff_session_cookie_signs_into_the_admin(self):
        self.user.is_staff = True
        self.user.save()
        self.client.cookies["access_token"] = str(RefreshToken.for_user(self.user).access_token)

        response = self.client.get("/api/admin/login/?next=/api/admin/")

        self.assertRedirects(response, "/api/admin/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_without_a_session_you_sign_in_first(self):
        response = self.client.get("/api/admin/login/")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("http://localhost:3000/login?next="))

    def test_a_member_who_isnt_staff_is_refused(self):
        self.client.cookies["access_token"] = str(RefreshToken.for_user(self.user).access_token)

        response = self.client.get("/api/admin/login/")

        self.assertEqual(response.status_code, 403)


class UserModelTests(PlatformTestCase):
    def test_the_system_user_always_exists_with_a_fixed_id(self):
        system = User.objects.get(pk=User.SYSTEM_ID)

        self.assertEqual(str(system.pk), "00000000-0000-0000-0000-000000000001")
        self.assertFalse(system.is_active)
        self.assertFalse(system.has_usable_password())

    def test_email_is_normalised_to_lowercase(self):
        self.assertEqual(
            User.objects.create_user(email="Mixed@Example.COM").email, "mixed@example.com"
        )

    def test_createsuperuser_is_refused(self):
        with self.assertRaises(NotImplementedError):
            User.objects.create_superuser(email="admin@example.com", password="x")


class CommandTests(PlatformTestCase):
    def test_make_superuser_promotes_and_revokes(self):
        call_command("make_superuser", self.user.email, stdout=io.StringIO())
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_superuser and self.user.is_staff)

        call_command("make_superuser", self.user.email, "--revoke", stdout=io.StringIO())
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser or self.user.is_staff)

    def test_make_superuser_needs_an_existing_account(self):
        with self.assertRaises(CommandError):
            call_command("make_superuser", "nobody@example.com")

    @override_settings(DEBUG=True)
    def test_login_as_creates_the_account_and_prints_a_sign_in_link(self):
        out = io.StringIO()
        call_command("login_as", "dev@example.com", stdout=out)

        self.assertTrue(User.objects.filter(email="dev@example.com").exists())
        self.assertIn("http://localhost:3000/auth/dev-login?access=", out.getvalue())

    def test_login_as_refuses_outside_debug(self):
        with self.assertRaises(CommandError):
            call_command("login_as", "dev@example.com")
