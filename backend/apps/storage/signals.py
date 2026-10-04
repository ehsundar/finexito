from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.storage.models import StoredObject


@receiver(post_delete, sender=StoredObject)
def remove_file(sender, instance, **kwargs):
    # After commit, so a rolled-back delete still has its file.
    backend, key = instance.backend, instance.key
    transaction.on_commit(lambda: backend.delete(key))
