"""A StoredObject is one uploaded file: a ticket first, then the file in its location."""

from django.conf import settings
from django.core.files.storage import StorageHandler
from django.db import models
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel
from apps.storage.formats import FORMATS

# The configured locations, each built once on first use.
locations = StorageHandler(settings.STORAGE_LOCATIONS)


class ObjectStatus(models.TextChoices):
    PENDING = "pending", _("Waiting for the upload")
    CHECKING = "checking", _("Uploaded, being checked")
    READY = "ready", _("Uploaded")


class StoredObjectQuerySet(models.QuerySet):
    def ready(self):
        return self.filter(status=ObjectStatus.READY)

    def stale(self, now=None):
        """Tickets whose upload never finished before they expired."""
        return self.exclude(status=ObjectStatus.READY).filter(expires_at__lte=now or tz.now())


class StoredObject(BaseModel):
    # The one account allowed to upload the file. Once it is there, access is
    # decided by its location (public or signed links), not by owner.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stored_objects"
    )
    scope = models.CharField(max_length=50, blank=True, help_text=_("The app it belongs to."))
    location = models.CharField(
        max_length=50, help_text=_("Where the file lives: a name in STORAGE_LOCATIONS.")
    )
    key = models.CharField(max_length=255, unique=True, help_text=_("Its name in the location."))
    content_type = models.CharField(max_length=100, choices=[(t, t) for t in FORMATS])
    size = models.PositiveBigIntegerField(help_text=_("The exact bytes the upload must be."))
    status = models.CharField(max_length=20, choices=ObjectStatus, default=ObjectStatus.PENDING)
    expires_at = models.DateTimeField(help_text=_("The upload must finish before this."))

    sha256 = models.CharField(max_length=64, blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)

    objects = StoredObjectQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        verbose_name = _("stored object")
        verbose_name_plural = _("stored objects")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "expires_at"))]

    def __str__(self) -> str:
        return f"{self.id} ({self.content_type})"

    @property
    def backend(self):
        return locations[self.location]

    @property
    def is_ready(self) -> bool:
        return self.status == ObjectStatus.READY
