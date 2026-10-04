"""Storage operations for other apps. Nothing here trusts what an uploader sends.

The flow is the same wherever the file goes, like a presigned S3 upload::

    obj = services.create_upload(
        user, scope="todos", folder="comments", storage_class="private",
        content_type="image/png", size=2_000_000,
    )
    services.upload_url(obj)     # the user PUTs exactly those bytes to it,
                                 # then POSTs storage/uploads/<id>/complete/
    ...
    services.object_url(obj)     # once obj.is_ready: a link anyone holding it can open
"""

import hashlib
import os
import re
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone as tz

from apps.storage.formats import FORMATS, HEAD_SIZE
from apps.storage.models import ObjectStatus, StoredObject

CHUNK_SIZE = 64 * 1024
# Path segments an app may name its scope and folders with.
SEGMENTS = re.compile(r"[a-z0-9_-]+(/[a-z0-9_-]+)*")


class UploadError(Exception):
    """Why an upload was refused. ``status`` is the HTTP status to answer with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# --- tickets -------------------------------------------------------------------


def create_upload(
    owner,
    *,
    scope: str,
    content_type: str,
    size: int,
    storage_class: str = "public",
    folder: str = "",
    ttl: timedelta | None = None,
    **extra,
) -> StoredObject:
    """A ticket letting ``owner``, and only them, upload one file of this type.

    ``scope`` is the calling app's label. It and ``folder`` make up the start of
    the file's key; ``storage_class`` (a name in STORAGE_CLASSES) picks where it lives.
    """
    if content_type not in FORMATS:
        raise ValueError(f"{content_type!r} is not an accepted type: {', '.join(FORMATS)}.")
    if not 0 < size <= settings.STORAGE_MAX_UPLOAD_BYTES:
        raise ValueError(f"size must be 1..{settings.STORAGE_MAX_UPLOAD_BYTES} bytes.")
    if storage_class not in settings.STORAGE_CLASSES:
        raise ValueError(f"{storage_class!r} is not one of {', '.join(settings.STORAGE_CLASSES)}.")
    prefix = f"{scope}/{folder}".strip("/")
    if not SEGMENTS.fullmatch(prefix):
        raise ValueError(f"{prefix!r} is not a valid scope and folder.")
    pk = uuid.uuid4()
    return StoredObject.objects.create(
        id=pk,
        owner=owner,
        scope=scope,
        location=settings.STORAGE_CLASSES[storage_class],
        key=f"{prefix}/{pk.hex}.{FORMATS[content_type].extension}",
        content_type=content_type,
        size=size,
        expires_at=tz.now() + (ttl or settings.STORAGE_UPLOAD_TTL),
        extra=extra,
    )


def upload_url(obj: StoredObject) -> str:
    return obj.backend.upload_url(obj)


# --- receiving (LocalStorage; a bucket takes the PUT itself) ----------------


def receive_upload(obj: StoredObject, stream, *, content_type: str, length: int | None):
    """Stream the request body into place, holding it to what a bucket would.

    The file is written to a temporary name and only linked into place once all
    of it has arrived, so a half-written file is never served, and a file that
    is already there is never replaced.
    """
    if obj.status != ObjectStatus.PENDING:
        raise UploadError("This object has already been uploaded.", 409)
    if obj.expires_at <= tz.now():
        raise UploadError("This upload link has expired.", 410)
    if content_type.split(";")[0].strip().lower() != obj.content_type:
        raise UploadError(f"Send the file as {obj.content_type}.", 415)
    if length is None:
        raise UploadError("Send a Content-Length.", 411)
    if length != obj.size:
        raise UploadError(f"The file must be {obj.size} bytes.", 413)

    path = Path(obj.backend.path(obj.key))
    tmp = _tmp_dir() / uuid.uuid4().hex
    try:
        _write(stream, tmp, length)
        tmp.chmod(0o644)
        path.parent.mkdir(parents=True, exist_ok=True)
        os.link(tmp, path)
    except FileExistsError as error:
        raise UploadError("This object has already been uploaded.", 409) from error
    finally:
        tmp.unlink(missing_ok=True)


def _write(stream, tmp: Path, length: int):
    size = 0
    with tmp.open("xb") as out:
        while size < length:
            chunk = stream.read(min(CHUNK_SIZE, length - size))
            if not chunk:
                break
            size += len(chunk)
            out.write(chunk)
        out.flush()
        os.fsync(out.fileno())
    if size != length:
        raise UploadError("The upload ended before Content-Length bytes arrived.")


def _tmp_dir() -> Path:
    # Inside STORAGE_ROOT, so the final link is on the same filesystem.
    path = Path(settings.STORAGE_ROOT) / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- completing ----------------------------------------------------------------------


def complete_upload(obj: StoredObject) -> StoredObject:
    """Check the file that arrived against the ticket, and mark it ready.

    A file that fails is deleted and the ticket goes back to pending, so the
    upload can be retried until it expires.
    """
    if obj.is_ready:
        return obj
    # Claimed with a conditional update, so two checks cannot run at once.
    claimed = StoredObject.objects.filter(
        pk=obj.pk, status=ObjectStatus.PENDING, expires_at__gt=tz.now()
    ).update(status=ObjectStatus.CHECKING)
    if not claimed:
        obj.refresh_from_db()
        if obj.is_ready:
            return obj
        if obj.status == ObjectStatus.PENDING:
            raise UploadError("This upload link has expired.", 410)
        raise UploadError("This object is already being checked.", 409)

    try:
        if not obj.backend.exists(obj.key):
            raise UploadError("The file hasn't arrived yet.", 409)
        try:
            size, head, digest = _read(obj)
            if size != obj.size:
                raise UploadError(f"The file must be {obj.size} bytes.", 413)
            if not FORMATS[obj.content_type].matches(head):
                raise UploadError(f"The file is not a valid {obj.content_type}.", 415)
        except UploadError:
            obj.backend.delete(obj.key)
            raise
    except BaseException:
        StoredObject.objects.filter(pk=obj.pk).update(status=ObjectStatus.PENDING)
        raise

    obj.status = ObjectStatus.READY
    obj.sha256 = digest
    obj.uploaded_at = tz.now()
    obj.save(update_fields=("status", "sha256", "uploaded_at", "updated_at"))
    return obj


def _read(obj: StoredObject) -> tuple[int, bytes, str]:
    sha = hashlib.sha256()
    size = 0
    head = b""
    with obj.backend.open(obj.key, "rb") as file:
        while chunk := file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > obj.size:
                break
            if len(head) < HEAD_SIZE:
                head += chunk[: HEAD_SIZE - len(head)]
            sha.update(chunk)
    return size, head, sha.hexdigest()


# --- serving -----------------------------------------------------------------------


def object_url(obj: StoredObject, *, expires_in: timedelta = timedelta(hours=1)) -> str:
    """A link to a ready object: its cached public URL, or a signed private one."""
    return obj.backend.object_url(obj, expires_in)


# --- housekeeping ------------------------------------------------------------------


def purge(*, now=None) -> dict[str, int]:
    """Drop expired tickets, with any file they got, and leftover temporary files."""
    now = now or tz.now()
    counts = {"tickets": 0, "temporary": 0}

    counts["tickets"], _ = StoredObject.objects.stale(now).delete()

    # A crash mid-upload can leave one behind; nothing live is older than a ticket.
    cutoff = (now - settings.STORAGE_UPLOAD_TTL - timedelta(hours=1)).timestamp()
    for tmp in (Path(settings.STORAGE_ROOT) / "tmp").glob("*"):
        if tmp.is_file() and tmp.stat().st_mtime < cutoff:
            tmp.unlink(missing_ok=True)
            counts["temporary"] += 1
    return counts
