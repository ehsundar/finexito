from django.urls import reverse

from apps.common.testing import PASSWORD, PlatformTestCase, User
from apps.profiles import services
from apps.profiles.models import Profile, ProfileStatus


class ProfileEndpointTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.profile = services.create_profile(self.user, display_name="Someone")
        self.authenticate()

    def test_me_returns_the_callers_profile(self):
        response = self.client.get(reverse("profile-me"))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["display_name"], "Someone")
        self.assertEqual(response.data["email"], self.user.email)

    def test_me_creates_a_missing_profile(self):
        stranger = User.objects.create_user(email="stranger@example.com", password=PASSWORD)
        self.client.force_authenticate(user=stranger)

        response = self.client.get(reverse("profile-me"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["display_name"], "stranger")
        self.assertTrue(Profile.objects.filter(user=stranger).exists())

    def test_me_requires_authentication(self):
        self.client.force_authenticate(user=None)

        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 401)

    def test_me_patch_updates_editable_fields_only(self):
        response = self.client.patch(
            reverse("profile-me"), {"display_name": "Renamed", "role": "admin"}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.display_name, "Renamed")
        self.assertEqual(self.profile.role, "member")

    def test_me_patch_stores_data_as_strings(self):
        response = self.client.patch(
            reverse("profile-me"), {"data": {"theme": "dark", "newsletter": ""}}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.data, {"theme": "dark", "newsletter": ""})

    def test_me_patch_rejects_non_string_data_values(self):
        for data in ({"count": 3}, {"nested": {"a": "b"}}, {"missing": None}, ["nope"]):
            with self.subTest(data=data):
                response = self.client.patch(reverse("profile-me"), {"data": data}, format="json")

                self.assertEqual(response.status_code, 400)
                self.assertIn("data", response.data["error"]["fields"])

    def test_suspended_profile_cannot_use_me(self):
        self.profile.status = ProfileStatus.SUSPENDED
        self.profile.save(update_fields=["status"])

        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 403)


class MemberListTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        services.create_profile(self.user, display_name="Someone")
        self.authenticate()

    def test_members_list_shows_active_profiles_only(self):
        other = User.objects.create_user(email="other@example.com", password=PASSWORD)
        services.create_profile(other, display_name="Other")
        gone = User.objects.create_user(email="gone@example.com", password=PASSWORD)
        services.create_profile(gone, display_name="Gone", status=ProfileStatus.SUSPENDED)

        response = self.client.get(reverse("member-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["display_name"] for row in response.data["results"]], ["Other", "Someone"]
        )
