"""A Program is one app/website served by this instance.

Each program switches on the subset of platform apps it needs (``enabled_apps``)
and carries its own defaults, so a new side project is a database row rather
than a new deployment.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel


class Program(BaseModel):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Platform apps this program uses, e.g. ["profiles", "store", "payments"].
    # A feature checks this before serving anything for the program.
    enabled_apps = models.JSONField(default=list, blank=True)

    # Anyone with an account may enrol themselves; otherwise enrolment is by
    # invitation or admin action only.
    allow_self_enrolment = models.BooleanField(default=True)

    # Defaults every profile in this program inherits until it overrides them.
    default_settings = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("program")
        verbose_name_plural = _("programs")
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def has_app(self, app_label: str) -> bool:
        return app_label in (self.enabled_apps or [])


class ProgramDomain(BaseModel):
    """Maps a hostname to a program, so the frontend need not send a header."""

    program = models.ForeignKey(Program, related_name="domains", on_delete=models.CASCADE)
    host = models.CharField(max_length=253, unique=True, db_index=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ("-is_primary", "host")

    def __str__(self) -> str:
        return self.host

    def save(self, *args, **kwargs):
        self.host = self.host.strip().lower()
        super().save(*args, **kwargs)
