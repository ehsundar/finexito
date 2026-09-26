"""Base models shared by every platform app."""

import uuid

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Public-facing primary key, so IDs can be exposed without leaking counts."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    # Free-form string-to-string attributes. Whoever owns a key decides what its
    # value means; the ``Extra*Field`` descriptors in ``common.fields`` cover the common types.
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True
