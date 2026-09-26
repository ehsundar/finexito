# storage

A small S3-like file store on the server's own disk. Backend code opens an
upload ticket for one user, the user sends the file to a single-use link, and
the file is then served with CDN-friendly cache headers. No external service.

## Flow

```python
from apps.storage import services

obj = services.create_upload(
    user, content_type="image/png", max_size=2_000_000,  # bytes
    visibility="public",                                  # or "private"
)
services.upload_url(obj)   # -> /api/v1/storage/uploads/<id>/, give it to the user

# The user's client:  PUT <upload url>   (JWT or session)
#                     Content-Type: image/png
#                     <raw file bytes>
# -> 200 with the object, including its `url`

obj.refresh_from_db()
if obj.is_ready:
    services.object_url(obj)   # public: /api/media/<key>; private: a signed link
```

Any keyword arguments to `create_upload` beyond those go into `extra`, e.g. to
note what the file is for.

## Model

`StoredObject` extends `common.models.BaseModel`.

| Field          | Meaning                                                              |
| -------------- | -------------------------------------------------------------------- |
| `owner`        | The only account allowed to upload.                                  |
| `content_type` | One of `formats.FORMATS`. Fixed by the ticket.                       |
| `max_size`     | Upper bound for the upload, at most `STORAGE_MAX_UPLOAD_BYTES`.      |
| `visibility`   | `public` (cached by anyone) / `private` (signed links only).         |
| `status`       | `pending` -> `uploading` -> `ready`. A failed upload goes back to `pending`. |
| `expires_at`   | The upload must finish before this (`STORAGE_UPLOAD_TTL_MINUTES`, 30). |
| `size`, `sha256`, `uploaded_at` | Filled in once the file is stored.                  |

A ready file never changes: to replace one, open a new ticket and delete the
old row. Deleting a row (directly, in the admin or with its owner) deletes the
file.

## On disk

`STORAGE_ROOT` (`backend/media/` locally, the `storage` volume at `/srv/storage` on the server):

```
public/ab/ab12…ef.png    served as-is at /api/media/ab/ab12…ef.png
private/cd/cd34…01.pdf   only through signed links
tmp/                     uploads in progress
```

The path comes only from the id and the type's extension, never from anything
the uploader sent.

## Serving

**Public** files are served by Caddy straight from `public/` with
`Cache-Control: public, max-age=31536000, immutable`. A missing file is not
cached, since its upload may still be on its way. Locally, `runserver` serves
them (`DEBUG` only).

**Private** files go through `GET /api/v1/storage/objects/<id>/?expires=…&signature=…`.
Django checks the HMAC signature and expiry and then answers with
`X-Accel-Redirect`. Caddy sends the file from `private/`, which it never serves
directly, so no gunicorn worker is spent streaming it. The response is
`Cache-Control: private` for the link's remaining lifetime. Links are rounded
to the `expires_in` window, so repeated calls return the same, cacheable URL.
Whoever holds a link can open the file: hand links only to people who may see it.

## Defences

| Attack                            | Defence                                                      |
| --------------------------------- | ------------------------------------------------------------ |
| Uploading for someone else        | Only the ticket's owner, authenticated; others get `404`.    |
| Replaying or racing an upload     | One upload per ticket, claimed atomically; `409` after.      |
| Stored XSS (HTML, SVG, JS)        | Allow-list of binary types, checked against the file's first bytes; `nosniff`; `CSP: sandbox`; Content-Type from the fixed extension. |
| Path traversal                    | Keys built from the UUID only.                               |
| Filling the disk                  | Per-ticket `max_size`, a global cap enforced by Caddy and Django, tickets expire, `purge_storage` clears leftovers. |
| Slow uploads tying up workers     | Caddy buffers the body before Django sees it.                |
| Guessing private URLs             | Not served by Caddy at all; signed, expiring links.          |
| Half-written files being served   | Written to `tmp/`, fsynced, then renamed into place.         |

## Housekeeping

`python manage.py purge_storage` deletes expired tickets, stale `tmp/` files
and files with no row. It runs on every deploy (in the `migrate` service).

## Settings

| Setting                      | Default   |                                                  |
| ---------------------------- | --------- | ------------------------------------------------ |
| `STORAGE_ROOT`               | `media/`  | Pinned to `/srv/storage` in `deploy/compose.yml`. |
| `STORAGE_MAX_UPLOAD_BYTES`   | 25 MiB    | Keep equal to `max_size` in `deploy/Caddyfile`.  |
| `STORAGE_UPLOAD_TTL_MINUTES` | 30        |                                                  |
| `STORAGE_ACCEL_REDIRECT`     | off       | On in production, where Caddy serves private files. |

## Adding a type

Add it to `formats.FORMATS` with its extension and magic bytes, then make a
migration (the field's choices change). Never add a type a browser would run
or render as a page.
