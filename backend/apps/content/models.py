"""A Page is a piece of Markdown content written in the admin and read on the site."""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel

# Generous for an article, small enough that one page cannot bloat a response.
MAX_BODY_LENGTH = 100_000


class PageVisibility(models.TextChoices):
    PUBLIC = "public", _("Public")
    PRIVATE = "private", _("Signed-in members only")


class PageStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    PUBLISHED = "published", _("Published")


class PageQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=PageStatus.PUBLISHED, published_at__lte=tz.now())

    def visible_to(self, user):
        """Published pages the caller may read: everything, or public ones only."""
        pages = self.published()
        if user is None or not user.is_authenticated:
            pages = pages.filter(visibility=PageVisibility.PUBLIC)
        return pages


class Page(BaseModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=100, unique=True, help_text=_("The page lives at /pages/<slug>.")
    )
    summary = models.CharField(
        max_length=300, blank=True, help_text=_("Shown in listings and link previews.")
    )
    body = models.TextField(blank=True, help_text=_("Markdown. Raw HTML is shown as text."))

    visibility = models.CharField(
        max_length=20, choices=PageVisibility, default=PageVisibility.PUBLIC
    )
    status = models.CharField(max_length=20, choices=PageStatus, default=PageStatus.DRAFT)
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Set when first published. A future time schedules the page."),
    )

    objects = PageQuerySet.as_manager()

    class Meta:
        verbose_name = _("page")
        verbose_name_plural = _("pages")
        ordering = ("-published_at", "-created_at")

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return f"/pages/{self.slug}"

    def clean(self):
        super().clean()
        self.title = self.title.strip()
        errors = {}
        if not self.title:
            errors["title"] = _("A page needs a title.")
        if len(self.body) > MAX_BODY_LENGTH:
            errors["body"] = _("Keep the body under %(max)s characters.") % {"max": MAX_BODY_LENGTH}
        if self.status == PageStatus.PUBLISHED and not self.body.strip():
            errors["body"] = _("A published page needs a body.")
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.status == PageStatus.PUBLISHED and self.published_at is None:
            self.published_at = tz.now()
        super().save(*args, **kwargs)
