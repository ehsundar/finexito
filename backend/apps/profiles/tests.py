from django.urls import reverse

from apps.common.testing import PASSWORD, PlatformTestCase, User
from apps.profiles import services
from apps.profiles.models import Profile, ProfileSetting, ProfileStatus
from apps.programs.models import Program


class EnrolmentServiceTests(PlatformTestCase):
    def test_enrol_is_idempotent(self):
        first, created_first = services.enrol(self.user, self.program)
        second, created_second = services.enrol(self.user, self.program)

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Profile.objects.filter(user=self.user).count(), 1)

    def test_a_user_can_hold_one_profile_per_program(self):
        services.enrol(self.user, self.program)
        services.enrol(self.user, self.closed_program)

        self.assertEqual(Profile.objects.filter(user=self.user).count(), 2)

    def test_enrolling_in_a_closed_program_is_pending(self):
        created, _ = services.enrol(self.user, self.closed_program)

        self.assertEqual(created.status, ProfileStatus.PENDING)


class ProfileEndpointTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.profile, _ = services.enrol(self.user, self.program, display_name="Someone")
        self.authenticate()

    def test_me_returns_the_profile_for_the_current_program(self):
        response = self.client.get(reverse("profile-me"))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["program"], self.program.slug)
        self.assertEqual(response.data["display_name"], "Someone")

    def test_me_is_denied_when_not_enrolled(self):
        stranger = User.objects.create_user(email="stranger@example.com", password=PASSWORD)
        self.client.force_authenticate(user=stranger)

        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 403)

    def test_me_requires_a_resolved_program(self):
        self.anonymous_client.force_authenticate(user=self.user)

        self.assertEqual(self.anonymous_client.get(reverse("profile-me")).status_code, 404)

    def test_me_patch_updates_editable_fields_only(self):
        response = self.client.patch(
            reverse("profile-me"), {"display_name": "Renamed", "role": "admin"}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.display_name, "Renamed")
        self.assertEqual(self.profile.role, "member")

    def test_suspended_profile_cannot_use_me(self):
        self.profile.status = ProfileStatus.SUSPENDED
        self.profile.save(update_fields=["status"])

        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 403)


class SettingsEndpointTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.profile, _ = services.enrol(self.user, self.program, display_name="Someone")
        self.authenticate()
        self.url = reverse("profile-me-settings")

    def test_settings_start_as_the_program_defaults(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"theme": "light", "newsletter": False})

    def test_settings_patch_merges_over_the_defaults(self):
        response = self.client.patch(
            self.url, {"theme": "dark", "density": "compact"}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data, {"theme": "dark", "newsletter": False, "density": "compact"}
        )
        self.assertTrue(ProfileSetting.objects.filter(profile=self.profile, key="theme").exists())

    def test_setting_null_clears_the_override(self):
        self.client.patch(self.url, {"theme": "dark"}, format="json")

        response = self.client.patch(self.url, {"theme": None}, format="json")

        self.assertEqual(response.data["theme"], "light")
        self.assertFalse(ProfileSetting.objects.filter(profile=self.profile, key="theme").exists())

    def test_settings_reject_a_non_object_body(self):
        response = self.client.patch(self.url, ["nope"], format="json")

        self.assertEqual(response.status_code, 400)


class EnrolEndpointTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.authenticate()
        self.url = reverse("profile-enrol")

    def test_enrol_endpoint_joins_the_current_program(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Profile.objects.filter(user=self.user, program=self.program).exists())

    def test_enrol_endpoint_can_target_another_program(self):
        other = Program.objects.create(slug="other", name="Other")

        response = self.client.post(self.url, {"program": "other"}, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["program"], other.slug)

    def test_enrol_endpoint_refuses_a_closed_program(self):
        response = self.client.post(self.url, {"program": "closed"}, format="json")

        self.assertEqual(response.status_code, 403)


class ProfileVisibilityTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.profile, _ = services.enrol(self.user, self.program, display_name="Someone")
        self.authenticate()

    def test_listing_returns_every_profile_of_the_caller(self):
        services.enrol(self.user, self.closed_program)

        response = self.client.get(reverse("profile-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["program"] for row in response.data["results"]}, {"demo", "closed"})

    def test_listing_never_leaks_another_users_profiles(self):
        other_user = User.objects.create_user(email="other@example.com", password=PASSWORD)
        services.enrol(other_user, self.program)

        response = self.client.get(reverse("profile-list"))

        self.assertEqual([row["program"] for row in response.data["results"]], ["demo"])

    def test_members_list_is_scoped_to_the_current_program(self):
        elsewhere = User.objects.create_user(email="elsewhere@example.com", password=PASSWORD)
        services.enrol(elsewhere, self.closed_program)

        response = self.client.get(reverse("member-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["display_name"] for row in response.data["results"]], ["Someone"])
