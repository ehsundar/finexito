from io import StringIO

from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from apps.common.testing import PlatformTestCase
from apps.programs.models import Program, ProgramDomain


class ProgramResolutionTests(PlatformTestCase):
    def test_current_resolves_from_the_header(self):
        response = self.client.get(reverse("program-current"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slug"], self.program.slug)

    @override_settings(ALLOWED_HOSTS=["*"])
    def test_current_resolves_from_the_host(self):
        ProgramDomain.objects.create(program=self.program, host="demo.example.com", is_primary=True)

        response = self.anonymous_client.get(
            reverse("program-current"), HTTP_HOST="demo.example.com"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slug"], self.program.slug)

    def test_current_resolves_from_the_query_parameter(self):
        response = self.anonymous_client.get(
            reverse("program-current"), {"program": self.program.slug}
        )

        self.assertEqual(response.status_code, 200)

    def test_current_is_404_when_nothing_resolves(self):
        self.assertEqual(self.anonymous_client.get(reverse("program-current")).status_code, 404)

    def test_inactive_programs_are_not_resolved_or_listed(self):
        Program.objects.filter(pk=self.program.pk).update(is_active=False)

        current = self.client.get(reverse("program-current"))
        listed = self.client.get(reverse("program-list"))

        self.assertEqual(current.status_code, 404)
        self.assertNotIn(self.program.slug, [row["slug"] for row in listed.data["results"]])


class ProgramCatalogueTests(PlatformTestCase):
    def test_program_catalogue_is_public(self):
        response = self.anonymous_client.get(reverse("program-list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.program.slug, [row["slug"] for row in response.data["results"]])

    def test_has_app_reflects_enabled_apps(self):
        self.assertTrue(self.program.has_app("profiles"))
        self.assertFalse(self.program.has_app("store"))


class CreateProgramCommandTests(PlatformTestCase):
    def test_createprogram_command_creates_and_updates(self):
        out = StringIO()
        call_command(
            "createprogram",
            "blog",
            "--apps",
            "profiles,store",
            "--domain",
            "Blog.Example.com",
            stdout=out,
        )
        call_command("createprogram", "blog", "--name", "My Blog", stdout=out)

        created = Program.objects.get(slug="blog")
        self.assertEqual(created.name, "My Blog")
        self.assertEqual(ProgramDomain.objects.get(host="blog.example.com").program, created)
