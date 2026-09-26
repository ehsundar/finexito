"""Storage operations for other apps. Nothing here trusts what an uploader sends.

The flow, like a presigned S3 upload::

    obj = services.create_upload(user, content_type="image/png", max_size=2_000_000)
    services.upload_url(obj)     # hand this to the user; they PUT the raw bytes to it
    ...
    services.object_url(obj)     # once obj.is_ready: a link anyone holding it can open
"""

import hashlib
import os
import time
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone as tz
from django.utils.crypto import constant_time_compare

from apps.storage.formats import FORMATS, HEAD_SIZE
from apps.storage.models import ObjectStatus, ObjectVisibility, StoredObject

CHUNK_SIZE = 64 * 1024
SIGNING_SALT = "storage.object"


class UploadError(Exception):
    """Why an upload was refused. ``status`` is the HTTP status to answer with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# --- tickets -------------------------------------------------------------------


def create_upload(
    owner,
    *,
    content_type: str,
    max_size: int,
    visibility: str = ObjectVisibility.PUBLIC,
    ttl: timedelta | None = None,
    **extra,
) -> StoredObject:
    """A ticket letting ``owner``, and only them, upload one file of this type."""
    if content_type not in FORMATS:
        raise ValueError(f"{content_type!r} is not an accepted type: {', '.join(FORMATS)}.")
    if not 0 < max_size <= settings.STORAGE_MAX_UPLOAD_BYTES:
        raise ValueError(f"max_size must be 1..{settings.STORAGE_MAX_UPLOAD_BYTES} bytes.")
    return StoredObject.objects.create(
        owner=owner,
        content_type=content_type,
        max_size=max_size,
        visibility=visibility,
        expires_at=tz.now() + (ttl or settings.STORAGE_UPLOAD_TTL),
        extra=extra,
    )


def upload_url(obj: StoredObject) -> str:
    return reverse("storage-upload", kwargs={"pk": obj.pk})


# --- receiving -------------------------------------------------------------------


def receive_upload(obj: StoredObject, user, stream, *, content_type: str, length: int | None):
    """Stream the request body to disk, checking it against the ticket as it goes.

    The file is written to a temporary name and only moved into place once it is
    complete and recognised, so a half-written or rejected upload is never served.
    A refused upload leaves the ticket pending, to be retried until it expires.
    """
    if obj.owner_id != user.pk:
        raise UploadError("Not found.", 404)
    if obj.is_ready:
        raise UploadError("This object has already been uploaded.", 409)
    if content_type.split(";")[0].strip().lower() != obj.content_type:
        raise UploadError(f"Send the file as {obj.content_type}.", 415)
    if length is None:
        raise UploadError("Send a Content-Length.", 411)
    if length > obj.max_size:
        raise UploadError(f"The file may be at most {obj.max_size} bytes.", 413)
    if length == 0:
        raise UploadError("The file is empty.")

    # Claimed with a conditional update, so two concurrent uploads cannot both write.
    claimed = StoredObject.objects.filter(
        pk=obj.pk, status=ObjectStatus.PENDING, expires_at__gt=tz.now()
    ).update(status=ObjectStatus.UPLOADING)
    if not claimed:
        obj.refresh_from_db()
        if obj.status == ObjectStatus.PENDING:
            raise UploadError("This upload link has expired.", 410)
        raise UploadError("This object is already being uploaded.", 409)

    tmp = _tmp_dir() / uuid.uuid4().hex
    try:
        size, digest = _write(stream, tmp, obj, length)
        tmp.chmod(0o644)
        obj.path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, obj.path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        StoredObject.objects.filter(pk=obj.pk).update(status=ObjectStatus.PENDING)
        raise

    obj.status = ObjectStatus.READY
    obj.size = size
    obj.sha256 = digest
    obj.uploaded_at = tz.now()
    obj.save(update_fields=("status", "size", "sha256", "uploaded_at", "updated_at"))
    return obj


def _write(stream, tmp: Path, obj: StoredObject, length: int) -> tuple[int, str]:
    sha = hashlib.sha256()
    size = 0
    head = b""
    with tmp.open("xb") as out:
        while size < length:
            chunk = stream.read(min(CHUNK_SIZE, length - size))
            if not chunk:
                break
            size += len(chunk)
            if len(head) < HEAD_SIZE:
                head += chunk[: HEAD_SIZE - len(head)]
            sha.update(chunk)
            out.write(chunk)
        out.flush()
        os.fsync(out.fileno())
    if size != length:
        raise UploadError("The upload ended before Content-Length bytes arrived.")
    if not FORMATS[obj.content_type].matches(head):
        raise UploadError(f"The file is not a valid {obj.content_type}.", 415)
    return size, sha.hexdigest()


def _tmp_dir() -> Path:
    # Inside STORAGE_ROOT, so the final move is a rename on the same filesystem.
    path = Path(settings.STORAGE_ROOT) / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- serving -----------------------------------------------------------------------


def object_url(obj: StoredObject, *, expires_in: timedelta = timedelta(hours=1)) -> str:
    """A link to a ready object: the cached public URL, or a signed private one.

    Private links are rounded up to the next ``expires_in`` boundary, so links
    handed out in the same window are identical and the browser can cache them.
    """
    if obj.visibility == ObjectVisibility.PUBLIC:
        return f"{settings.MEDIA_URL}{obj.key}"
    step = max(int(expires_in.total_seconds()), 60)
    expires = (int(time.time()) // step + 2) * step
    path = reverse("storage-object", kwargs={"pk": obj.pk})
    return f"{path}?expires={expires}&signature={_signature(obj, expires)}"


def check_signature(obj: StoredObject, expires: str, signature: str) -> int | None:
    """Seconds the link has left, or None if it is forged or expired."""
    try:
        expires_at = int(expires)
    except (TypeError, ValueError):
        return None
    remaining = expires_at - int(time.time())
    if remaining <= 0 or not constant_time_compare(signature, _signature(obj, expires_at)):
        return None
    return remaining


def _signature(obj: StoredObject, expires: int) -> str:
    return signing.Signer(salt=SIGNING_SALT).signature(f"{obj.pk}:{expires}")


# --- housekeeping ------------------------------------------------------------------


def purge(*, now=None) -> dict[str, int]:
    """Drop expired tickets, leftover temporary files and files with no row."""
    now = now or tz.now()
    root = Path(settings.STORAGE_ROOT)
    counts = {"tickets": 0, "temporary": 0, "orphans": 0}

    counts["tickets"], _ = StoredObject.objects.stale(now).delete()

    # A crash mid-upload can leave one behind; nothing live is older than a ticket.
    cutoff = (now - settings.STORAGE_UPLOAD_TTL - timedelta(hours=1)).timestamp()
    for tmp in (root / "tmp").glob("*"):
        if tmp.is_file() and tmp.stat().st_mtime < cutoff:
            tmp.unlink(missing_ok=True)
            counts["temporary"] += 1

    for visibility in ObjectVisibility.values:
        files = {}
        for path in (root / visibility).glob("*/*"):
            try:
                files[uuid.UUID(path.stem)] = path
            except ValueError:
                continue
        known = set(
            StoredObject.objects.ready()
            .filter(pk__in=files, visibility=visibility)
            .values_list("pk", flat=True)
        )
        for pk, path in files.items():
            if pk not in known and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                counts["orphans"] += 1
    return counts
