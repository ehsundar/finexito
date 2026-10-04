"""What offline clients need beyond the plain API: which rows were deleted, and
which queued operations have already been applied.
"""

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from apps.todos.projects.models import Project, Section, member_left
from apps.todos.tasks.models import Label, Task


class Tombstone(models.Model):
    """A deleted row, kept ``TODOS_SYNC_TOMBSTONE_DAYS`` so clients can drop it too.

    Seen by ``user``, or, without one, by everyone in project ``project_id``.
    """

    kind = models.CharField(max_length=20)  # project, section, task or label
    object_id = models.UUIDField()
    project_id = models.UUIDField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    deleted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("tombstone")
        verbose_name_plural = _("tombstones")

    def __str__(self) -> str:
        return f"{self.kind} {self.object_id}"


class SyncOperation(models.Model):
    """A queued operation a client sent, by the id it gave it, so sending it twice
    applies it once."""

    id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    status = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("sync operation")
        verbose_name_plural = _("sync operations")

    def __str__(self) -> str:
        return str(self.id)


@receiver(pre_delete, sender=Project)
def project_deleted(sender, instance, **kwargs):
    # Before, while its members are still there to be told.
    Tombstone.objects.bulk_create(
        Tombstone(kind="project", object_id=instance.pk, user_id=user)
        for user in instance.people_ids()
    )


@receiver(member_left)
def project_left(sender, project, user, **kwargs):
    Tombstone.objects.create(kind="project", object_id=project.pk, user=user)


@receiver(post_delete, sender=Section)
@receiver(post_delete, sender=Task)
def row_deleted(sender, instance, **kwargs):
    kind = sender._meta.model_name
    Tombstone.objects.create(kind=kind, object_id=instance.pk, project_id=instance.project_id)


@receiver(post_delete, sender=Label)
def label_deleted(sender, instance, **kwargs):
    Tombstone.objects.create(kind="label", object_id=instance.pk, user_id=instance.owner_id)
