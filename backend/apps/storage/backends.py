"""The places a file can live, named in STORAGE_LOCATIONS. Each is a Django
storage that also hands out the two links a StoredObject needs: one to upload
it, one to open it. Uploads are refused unless they are exactly the ticket's
size and type, and never overwrite a file already there.
"""

import os
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.utils import timezone as tz
from django.utils.crypto import constant_time_compare
from storages.backends.s3 import S3Storage


class LocalStorage(FileSystemStorage):
    """A directory under STORAGE_ROOT. Uploads come through our own PUT view;
    public files are served under MEDIA_URL, private ones through signed links."""

    def __init__(self, *, directory: str, public: bool):
        super().__init__()
        self.directory = directory
        self.public = public

    # Read on every use rather than cached, so tests can move STORAGE_ROOT.
    @property
    def base_location(self):
        return Path(settings.STORAGE_ROOT) / self.directory

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def upload_url(self, obj) -> str:
        expires = int(obj.expires_at.timestamp())
        path = reverse("storage-upload", kwargs={"pk": obj.pk})
        return f"{path}?expires={expires}&signature={sign(obj, expires, 'upload')}"

    def object_url(self, obj, expires_in: timedelta) -> str:
        """Private links are rounded up to the next ``expires_in`` boundary, so
        links handed out in the same window are identical and the browser can
        cache them."""
        if self.public:
            return self.url(obj.key)
        step = max(int(expires_in.total_seconds()), 60)
        expires = (int(time.time()) // step + 2) * step
        path = reverse("storage-object", kwargs={"pk": obj.pk})
        return f"{path}?expires={expires}&signature={sign(obj, expires, 'object')}"


class BucketStorage(S3Storage):
    """A bucket on any S3-compatible service (R2, S3, MinIO…) that honours
    If-None-Match on PUT. The browser uploads to it directly with a presigned
    PUT; public files are served from the bucket's custom domain."""

    def __init__(self, **options):
        super().__init__(signature_version="s3v4", **options)
        self.public = not self.querystring_auth

    def upload_url(self, obj) -> str:
        # Length and type are signed in, and If-None-Match makes it write-once.
        return self.connection.meta.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": obj.key,
                "ContentType": obj.content_type,
                "ContentLength": obj.size,
                "IfNoneMatch": "*",
            },
            ExpiresIn=max(int((obj.expires_at - tz.now()).total_seconds()), 1),
        )

    def object_url(self, obj, expires_in: timedelta) -> str:
        return self.url(obj.key, expire=int(expires_in.total_seconds()))


def sign(obj, expires: int, purpose: str) -> str:
    return signing.Signer(salt=f"storage.{purpose}").signature(f"{obj.pk}:{expires}")


def check_signature(obj, expires, signature, purpose: str) -> int | None:
    """Seconds a LocalStorage link has left, or None if it is forged or expired."""
    try:
        expires_at = int(expires)
    except (TypeError, ValueError):
        return None
    remaining = expires_at - int(time.time())
    if remaining <= 0 or not constant_time_compare(signature or "", sign(obj, expires_at, purpose)):
        return None
    return remaining
