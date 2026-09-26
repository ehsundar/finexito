"""A Profile is everything the app knows about a person beyond their identity.

Each account has exactly one profile, which keeps ``accounts.User`` thin.
"""

from django.conf import settings as django_settings
from django.db import models
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel


class ProfileRole(models.TextChoices):
    MEMBER = "member", _("Member")
    MODERATOR = "moderator", _("Moderator")
    ADMIN = "admin", _("Admin")


class ProfileStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    PENDING = "pending", _("Pending")
    SUSPENDED = "suspended", _("Suspended")


class Profile(BaseModel):
    user = models.OneToOneField(
        django_settings.AUTH_USER_MODEL, related_name="profile", on_delete=models.CASCADE
    )

    display_name = models.CharField(max_length=150, blank=True)
    avatar_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    locale = models.CharField(max_length=16, default="en-gb")
    timezone = models.CharField(max_length=64, default="UTC")

    role = models.CharField(max_length=20, choices=ProfileRole, default=ProfileRole.MEMBER)
    status = models.CharField(max_length=20, choices=ProfileStatus, default=ProfileStatus.ACTIVE)
    enrolled_at = models.DateTimeField(default=tz.now)

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")
        ordering = ("-enrolled_at",)

    def __str__(self) -> str:
        return self.display_name or self.user.email

    @property
    def is_active(self) -> bool:
        return self.status == ProfileStatus.ACTIVE
