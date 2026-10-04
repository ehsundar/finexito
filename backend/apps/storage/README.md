# storage

Uploaded files, kept in buckets on an S3-compatible service (we use Cloudflare
R2) or on the server's own disk, behind one
S3-like flow. Backend code opens an upload ticket for one user, the user sends
the file straight to where it will live, and storage checks it before anyone
can use it.

## Flow

```python
from apps.storage import services

obj = services.create_upload(
    user,
    scope="todos",  # the calling app's label: the start of the key
    folder="comments",  # optional, the app's own folders below it
    storage_class="private",  # a name in STORAGE_CLASSES: where it lives
    content_type="image/png",
    size=2_000_000,  # exactly the bytes that will be sent
)
services.upload_url(obj)  # give it to the user

# The user's client:  PUT <upload url>          (no credentials: the link is signed)
#                     Content-Type: image/png
#                     If-None-Match: *
#                     <exactly `size` raw bytes>
#                     POST /api/v1/storage/uploads/<id>/complete/   (as the owner)
# -> 200 with the object, including its `url`

obj.refresh_from_db()
if obj.is_ready:
    services.object_url(obj)  # public: a cacheable URL; private: a signed link
```

Any keyword arguments to `create_upload` beyond those go into `extra`, e.g. to
note what the file is for.

## Classes and locations

An app picks a **class** (`public` or `private`). The class picks a
**location**, a named Django storage in `STORAGE_LOCATIONS`, and each row keeps
the location and key it was given. Pointing a class somewhere else changes only
where new files go; old ones stay where they are, so a location is retired only
once no row names it.

| Location        | Backend                   | Upload                    | Opened from                          |
|-----------------|---------------------------|---------------------------|--------------------------------------|
| `bucket-public` | `BucketStorage` (S3Storage) | presigned PUT, to the bucket | `https://<FINEXITO_STORAGE_PUBLIC_DOMAIN>/<key>` |
| `bucket-private`| `BucketStorage`           | presigned PUT, to the bucket | presigned GET, an hour                |
| `local-public`  | `LocalStorage` (FileSystemStorage) | signed PUT, to this API | `/api/media/<key>`, served by Caddy |
| `local-private` | `LocalStorage`            | signed PUT, to this API   | signed link, see below               |

A class goes to a bucket once one is set (`FINEXITO_STORAGE_PUBLIC_BUCKET`,
`FINEXITO_STORAGE_PRIVATE_BUCKET`), and to the server's disk until then; local
development needs no bucket. Both backends hold an upload to the same rules,
so swapping one for the other changes nothing for the client: exactly the
ticket's size and type (signed into the bucket's link), and never over a file
already there (`If-None-Match: *`).

## Model

`StoredObject` extends `common.models.BaseModel`.

| Field                   | Meaning                                                                         |
|-------------------------|---------------------------------------------------------------------------------|
| `owner`                 | The only account that may complete the upload.                                  |
| `scope`                 | The app it belongs to.                                                          |
| `location`, `key`       | Where the file is: `<scope>/<folder>/<id>.<ext>` in that location.              |
| `content_type`          | One of `formats.FORMATS`. Fixed by the ticket.                                  |
| `size`                  | Exactly the bytes to upload, at most `FINEXITO_STORAGE_MAX_UPLOAD_BYTES`.       |
| `status`                | `pending` -> `checking` -> `ready`. A failed check goes back to `pending`.      |
| `expires_at`            | The upload must finish before this (`FINEXITO_STORAGE_UPLOAD_TTL_MINUTES`, 30). |
| `sha256`, `uploaded_at` | Filled in once the file is checked.                                             |

A ready file never changes: to replace one, open a new ticket and delete the
old row. Deleting a row (directly, in the admin or with its owner) deletes the
file. Files from before locations existed keep their old keys
(`ab/ab12…ef.png`) in `local-public` and `local-private`.

## On the server's disk

`STORAGE_ROOT` (`backend/media/` locally, the `storage` volume at `/srv/storage` on the server):

```
public/todos/…/ab12…ef.png    served as-is at /api/media/<key>
private/todos/…/cd34…01.pdf   only through signed links
tmp/                          uploads in progress
```

**Public** files are served by Caddy straight from `public/` with
`Cache-Control: public, max-age=31536000, immutable`. Locally, `runserver`
serves them (`DEBUG` only).

**Private** files go through `GET /api/v1/storage/objects/<id>/?expires=…&signature=…`.
Django checks the signature and expiry and answers with `X-Accel-Redirect`;
Caddy sends the file from `private/`, which it never serves directly. Links
are rounded to the `expires_in` window, so repeated calls return the same,
cacheable URL. Whoever holds a link can open the file: hand links only to
people who may see it.

## Bucket setup

`BucketStorage` is plain S3 (django-storages); the service must honour
`If-None-Match` on PUT, as R2 and AWS S3 do. Two buckets, with a key scoped to
them (on R2, an API token with Object Read & Write). The public one has a
custom domain (on R2, r2.dev off); the private one no public access.
Both need CORS for the site's origin, since browsers upload to them directly:

```json
[{"AllowedOrigins": ["https://<site>"], "AllowedMethods": ["PUT", "GET", "HEAD"],
  "AllowedHeaders": ["Content-Type", "If-None-Match"], "MaxAgeSeconds": 3600}]
```

## Defences

| Attack                        | Defence                                                                                                  |
|-------------------------------|----------------------------------------------------------------------------------------------------------|
| Uploading for someone else    | Upload links are signed per ticket; only the owner can complete one; others get `404`.                    |
| Swapping a checked file       | Write-once (`If-None-Match: *`, a hard link locally); checks are claimed atomically.                     |
| Stored XSS (HTML, SVG, JS)    | Allow-list of binary types, checked against the file's first bytes; local files get `nosniff` and `CSP: sandbox`; buckets serve from another domain. |
| Path traversal                | Keys built from the app's own segments and the UUID only.                                                |
| Filling storage               | Exact size signed into each link, a global cap, tickets expire, `purge_storage` drops them with their files. |
| Slow uploads tying up workers | The bucket takes the upload itself; locally, Caddy buffers the body before Django sees it.                       |
| Half-written files            | Locally written to `tmp/`, fsynced, then linked into place; bucket writes are atomic.                        |

## Housekeeping

`python manage.py purge_storage` deletes expired tickets with whatever file
reached them, and stale `tmp/` files. It runs on every deploy (in the
`migrate` service).

## Settings

| Setting                                                         | Default  |                                                        |
|-----------------------------------------------------------------|----------|--------------------------------------------------------|
| `STORAGE_ROOT`                                                  | `media/` | Pinned to `/srv/storage` in `deploy/compose.yml`.      |
| `FINEXITO_STORAGE_MAX_UPLOAD_BYTES`                             | 25 MiB   | Keep equal to `max_size` in `deploy/Caddyfile`.        |
| `FINEXITO_STORAGE_UPLOAD_TTL_MINUTES`                           | 30       |                                                        |
| `FINEXITO_STORAGE_ACCEL_REDIRECT`                               | off      | On in production, where Caddy serves private files.    |
| `FINEXITO_STORAGE_ENDPOINT_URL`                                 |          | On R2, `https://<account id>.r2.cloudflarestorage.com` |
| `FINEXITO_STORAGE_REGION`                                       | `auto`   | `auto` on R2; the bucket's region elsewhere.           |
| `FINEXITO_STORAGE_ACCESS_KEY_ID`, `…_SECRET_ACCESS_KEY`         |          | The key for the buckets.                               |
| `FINEXITO_STORAGE_PUBLIC_BUCKET`, `…_PRIVATE_BUCKET`            | empty    | Empty keeps that class on the server's disk.           |
| `FINEXITO_STORAGE_PUBLIC_DOMAIN`                                |          | The public bucket's custom domain.                     |

## Adding a type

Add it to `formats.FORMATS` with its extension and magic bytes, then make a
migration (the field's choices change). Never add a type a browser would run
or render as a page.
