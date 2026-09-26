from datetime import timedelta

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone as tz

from apps.common.testing import PlatformTestCase
from apps.content.models import MAX_BODY_LENGTH, Page, PageStatus, PageVisibility


def make_page(slug, **fields):
    defaults = {"title": slug.title(), "body": "# Hello", "status": PageStatus.PUBLISHED}
    return Page.objects.create(slug=slug, **{**defaults, **fields})


class PageModelTests(PlatformTestCase):
    def test_publishing_stamps_published_at(self):
        page = make_page("about")

        self.assertIsNotNone(page.published_at)

    def test_drafts_have_no_published_at(self):
        self.assertIsNone(make_page("draft", status=PageStatus.DRAFT).published_at)

    def test_clean_rejects_a_blank_title(self):
        page = Page(title="   ", slug="blank", body="x")

        with self.assertRaises(ValidationError) as caught:
            page.full_clean()
        self.assertIn("title", caught.exception.message_dict)

    def test_clean_rejects_publishing_without_a_body(self):
        page = Page(title="Empty", slug="empty", status=PageStatus.PUBLISHED)

        with self.assertRaises(ValidationError) as caught:
            page.full_clean()
        self.assertIn("body", caught.exception.message_dict)

    def test_clean_rejects_an_oversized_body(self):
        page = Page(title="Huge", slug="huge", body="x" * (MAX_BODY_LENGTH + 1))

        with self.assertRaises(ValidationError) as caught:
            page.full_clean()
        self.assertIn("body", caught.exception.message_dict)

    def test_clean_rejects_a_bad_slug(self):
        page = Page(title="Bad", slug="not a slug/../x", body="x")

        with self.assertRaises(ValidationError) as caught:
            page.full_clean()
        self.assertIn("slug", caught.exception.message_dict)


class PageEndpointTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.public = make_page("public")
        self.private = make_page("private", visibility=PageVisibility.PRIVATE)
        self.draft = make_page("draft", status=PageStatus.DRAFT)
        self.scheduled = make_page("scheduled", published_at=tz.now() + timedelta(days=1))

    def slugs(self, response):
        return {page["slug"] for page in response.data["results"]}

    def test_anonymous_list_shows_public_pages_only(self):
        response = self.client.get(reverse("page-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.slugs(response), {"public"})
        self.assertNotIn("body", response.data["results"][0])

    def test_signed_in_list_includes_private_pages(self):
        self.authenticate()

        response = self.client.get(reverse("page-list"))

        self.assertEqual(self.slugs(response), {"public", "private"})

    def test_anonymous_can_read_a_public_page(self):
        response = self.client.get(reverse("page-detail", args=["public"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["body"], "# Hello")

    def test_anonymous_is_asked_to_sign_in_for_a_private_page(self):
        response = self.client.get(reverse("page-detail", args=["private"]))

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("body", response.data)

    def test_signed_in_can_read_a_private_page(self):
        self.authenticate()

        response = self.client.get(reverse("page-detail", args=["private"]))

        self.assertEqual(response.status_code, 200)

    def test_drafts_and_scheduled_pages_are_not_found(self):
        self.authenticate()

        for slug in ("draft", "scheduled", "missing"):
            response = self.client.get(reverse("page-detail", args=[slug]))
            self.assertEqual(response.status_code, 404, slug)
