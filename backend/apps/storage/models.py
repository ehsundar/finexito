"""A StoredObject is one uploaded file: a ticket first, then the file on disk."""

from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel
from apps.storage.formats import FORMATS


class ObjectVisibility(models.TextChoices):
    PUBLIC = "public", _("Public, served and cached by anyone")
    PRIVATE = "private", _("Private, only through signed links")


class ObjectStatus(models.TextChoices):
    PENDING = "pending", _("Waiting for the upload")
    UPLOADING = "uploading", _("Upload in progress")
    READY = "ready", _("Uploaded")


class StoredObjectQuerySet(models.QuerySet):
    def ready(self):
        return self.filter(status=ObjectStatus.READY)

    def stale(self, now=None):
        """Tickets whose upload never finished before they expired."""
        return self.exclude(status=ObjectStatus.READY).filter(expires_at__lte=now or tz.now())


class StoredObject(BaseModel):
    # The one account allowed to upload the file. Once it is there, access is
    # decided by visibility and signed links, not by owner.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stored_objects"
    )
    content_type = models.CharField(max_length=100, choices=[(t, t) for t in FORMATS])
    max_size = models.PositiveBigIntegerField(help_text=_("The most bytes the upload may be."))
    visibility = models.CharField(
        max_length=20, choices=ObjectVisibility, default=ObjectVisibility.PUBLIC
    )
    status = models.CharField(max_length=20, choices=ObjectStatus, default=ObjectStatus.PENDING)
    expires_at = models.DateTimeField(help_text=_("The upload must finish before this."))

    size = models.PositiveBigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)

    objects = StoredObjectQuerySet.as_manager()

    class Meta:
        verbose_name = _("stored object")
        verbose_name_plural = _("stored objects")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "expires_at"))]

    def __str__(self) -> str:
        return f"{self.id} ({self.content_type})"

    @property
    def key(self) -> str:
        """Where the file sits under its visibility's directory.

        Built only from the id and the type's extension, never from anything the
        uploader sent, so it cannot point outside the store. The two-character
        prefix keeps any one directory from growing huge.
        """
        return f"{self.id.hex[:2]}/{self.id.hex}.{FORMATS[self.content_type].extension}"

    @property
    def path(self) -> Path:
        return Path(settings.STORAGE_ROOT) / self.visibility / self.key

    @property
    def is_ready(self) -> bool:
        return self.status == ObjectStatus.READY
