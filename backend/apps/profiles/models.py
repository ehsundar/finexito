"""A Profile is a user's enrolment in one program.

One account, many profiles -- one per program the person has joined. Everything
a program knows about a person hangs off their profile, which keeps identity
(``accounts.User``) reusable across every app on the instance.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel
from apps.programs.models import Program


class ProfileRole(models.TextChoices):
    MEMBER = "member", _("Member")
    MODERATOR = "moderator", _("Moderator")
    ADMIN = "admin", _("Admin")


class ProfileStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    PENDING = "pending", _("Pending")
    SUSPENDED = "suspended", _("Suspended")


class Profile(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="profiles", on_delete=models.CASCADE
    )
    program = models.ForeignKey(Program, related_name="profiles", on_delete=models.CASCADE)

    display_name = models.CharField(max_length=150, blank=True)
    avatar_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    locale = models.CharField(max_length=16, default="en-gb")
    timezone = models.CharField(max_length=64, default="UTC")

    role = models.CharField(max_length=20, choices=ProfileRole, default=ProfileRole.MEMBER)
    status = models.CharField(max_length=20, choices=ProfileStatus, default=ProfileStatus.ACTIVE)
    enrolled_at = models.DateTimeField(default=tz.now)

    # Free-form, program-specific attributes. Anything a program needs that does
    # not warrant its own column lives here rather than in a new model.
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")
        ordering = ("-enrolled_at",)
        constraints = [
            models.UniqueConstraint(fields=("user", "program"), name="unique_profile_per_program")
        ]

    def __str__(self) -> str:
        return f"{self.display_name or self.user.email} @ {self.program.slug}"

    @property
    def is_active(self) -> bool:
        return self.status == ProfileStatus.ACTIVE

    def resolved_settings(self) -> dict:
        """Program defaults overlaid with this profile's own overrides."""
        resolved = dict(self.program.default_settings or {})
        resolved.update({s.key: s.value for s in self.settings.all()})
        return resolved


class ProfileSetting(BaseModel):
    """A single preference override, stored per key so it can be patched safely."""

    profile = models.ForeignKey(Profile, related_name="settings", on_delete=models.CASCADE)
    key = models.CharField(max_length=100)
    value = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ("key",)
        constraints = [
            models.UniqueConstraint(fields=("profile", "key"), name="unique_setting_per_profile")
        ]

    def __str__(self) -> str:
        return f"{self.profile_id}:{self.key}"
