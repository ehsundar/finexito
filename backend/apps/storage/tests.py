import io
import shutil
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone as tz

from apps.common.testing import PlatformTestCase
from apps.storage import services
from apps.storage.backends import BucketStorage, sign
from apps.storage.models import ObjectStatus, StoredObject

User = get_user_model()

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


class StorageTestCase(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        settings = override_settings(STORAGE_ROOT=self.root, MEDIA_ROOT=self.root / "public")
        settings.enable()
        self.addCleanup(settings.disable)

    def ticket(self, **fields):
        defaults = {"scope": "tests", "content_type": "image/png", "size": len(PNG)}
        return services.create_upload(self.user, **{**defaults, **fields})

    def put(self, obj, body=PNG, content_type="image/png", url=None):
        return self.client.generic(
            "PUT", url or services.upload_url(obj), body, content_type=content_type
        )

    def complete(self, obj):
        self.authenticate()
        response = self.client.post(reverse("storage-complete", kwargs={"pk": obj.pk}))
        self.client.force_authenticate(None)
        obj.refresh_from_db()
        return response

    def path(self, obj):
        return Path(obj.backend.path(obj.key))


class CreateUploadTests(StorageTestCase):
    def test_the_app_names_the_folder_and_the_class(self):
        obj = self.ticket(scope="todos", folder="comments", storage_class="private")

        self.assertEqual(obj.key, f"todos/comments/{obj.pk.hex}.png")
        self.assertEqual(obj.location, "local-private")

    def test_refuses_types_a_browser_could_run(self):
        for content_type in ("image/svg+xml", "text/html", "application/javascript"):
            with self.subTest(content_type), self.assertRaises(ValueError):
                self.ticket(content_type=content_type)

    @override_settings(STORAGE_MAX_UPLOAD_BYTES=500)
    def test_refuses_sizes_over_the_global_limit(self):
        with self.assertRaises(ValueError):
            self.ticket(size=501)

    def test_refuses_unknown_classes_and_odd_folders(self):
        for fields in ({"storage_class": "cold"}, {"folder": "../etc"}, {"scope": ""}):
            with self.subTest(fields), self.assertRaises(ValueError):
                self.ticket(**fields)


class UploadTests(StorageTestCase):
    def test_upload_then_complete_gives_a_public_url(self):
        obj = self.ticket()

        self.assertEqual(self.put(obj).status_code, 200)
        response = self.complete(obj)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(obj.status, ObjectStatus.READY)
        self.assertEqual(len(obj.sha256), 64)
        self.assertEqual(self.path(obj), self.root / "public" / obj.key)
        self.assertEqual(self.path(obj).read_bytes(), PNG)
        self.assertEqual(response.data["url"], f"/api/media/{obj.key}")
        self.assertEqual(list((self.root / "tmp").iterdir()), [])

    def test_only_a_signed_link_takes_the_file(self):
        obj = self.ticket()
        url = services.upload_url(obj)

        for name, link in (("unsigned", url.split("?")[0]), ("tampered", url[:-1] + "x")):
            with self.subTest(name):
                self.assertEqual(self.put(obj, url=link).status_code, 404)

    def test_refusals(self):
        cases = [
            ("wrong type", {"content_type": "image/jpeg"}, 415),
            ("wrong size", {"body": PNG + b"\x00"}, 413),
        ]
        for name, kwargs, code in cases:
            with self.subTest(name):
                obj = self.ticket()
                response = self.put(obj, **kwargs)
                self.assertEqual(response.status_code, code, response.data)
                self.assertFalse(self.path(obj).exists())

    def test_a_body_shorter_than_its_content_length_is_refused(self):
        obj = self.ticket()

        with self.assertRaises(services.UploadError):
            services.receive_upload(
                obj, io.BytesIO(PNG[:10]), content_type="image/png", length=len(PNG)
            )

        self.assertFalse(self.path(obj).exists())
        self.assertEqual(list((self.root / "tmp").iterdir()), [])

    def test_a_file_is_never_overwritten(self):
        obj = self.ticket()
        self.put(obj)

        self.assertEqual(self.put(obj, body=b"\x00" * len(PNG)).status_code, 409)
        self.assertEqual(self.path(obj).read_bytes(), PNG)

    def test_an_expired_ticket_is_refused(self):
        obj = self.ticket(ttl=timedelta(seconds=-1))

        self.assertEqual(self.put(obj).status_code, 404)  # its link has expired too
        self.assertEqual(self.complete(obj).status_code, 410)


class CompleteTests(StorageTestCase):
    def test_a_file_that_is_not_its_type_is_deleted(self):
        obj = self.ticket()
        self.put(obj, body=b"<html>" + b"\x00" * (len(PNG) - 6))

        self.assertEqual(self.complete(obj).status_code, 415)
        self.assertEqual(obj.status, ObjectStatus.PENDING)
        self.assertFalse(self.path(obj).exists())

    def test_nothing_uploaded_yet(self):
        obj = self.ticket()

        self.assertEqual(self.complete(obj).status_code, 409)
        self.assertEqual(obj.status, ObjectStatus.PENDING)

    def test_only_the_owner_completes(self):
        obj = self.ticket()
        self.put(obj)
        self.authenticate(User.objects.create_user(email="other@example.com"))

        response = self.client.post(reverse("storage-complete", kwargs={"pk": obj.pk}))

        self.assertEqual(response.status_code, 404)

    def test_completing_twice_is_harmless(self):
        obj = self.ticket()
        self.put(obj)
        self.complete(obj)

        self.assertEqual(self.complete(obj).status_code, 200)


class PrivateObjectTests(StorageTestCase):
    def setUp(self):
        super().setUp()
        self.obj = self.ticket(storage_class="private")
        self.put(self.obj)
        self.complete(self.obj)

    def test_lands_outside_the_public_directory(self):
        self.assertEqual(self.path(self.obj), self.root / "private" / self.obj.key)

    def test_a_signed_link_serves_it(self):
        response = self.client.get(services.object_url(self.obj))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), PNG)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response["Cache-Control"].startswith("private, max-age="))
        self.assertIn("sandbox", response["Content-Security-Policy"])

    @override_settings(STORAGE_ACCEL_REDIRECT=True)
    def test_behind_caddy_it_hands_the_file_over(self):
        response = self.client.get(services.object_url(self.obj))

        self.assertEqual(response["X-Accel-Redirect"], f"/{self.obj.key}")
        self.assertEqual(response.content, b"")

    def test_forged_or_expired_links_are_404(self):
        url = services.object_url(self.obj)
        base = url.split("?")[0]
        expired = int(time.time()) - 1
        upload = int(self.obj.expires_at.timestamp())
        for name, link in (
            ("tampered", url[:-1] + ("A" if url[-1] != "A" else "B")),
            ("unsigned", base),
            ("expired", f"{base}?expires={expired}&signature={sign(self.obj, expired, 'object')}"),
            (
                "upload link",
                f"{base}?expires={upload}&signature={sign(self.obj, upload, 'upload')}",
            ),
        ):
            with self.subTest(name):
                self.assertEqual(self.client.get(link).status_code, 404)


class HousekeepingTests(StorageTestCase):
    def test_deleting_a_row_deletes_its_file(self):
        obj = self.ticket()
        self.put(obj)
        path = self.path(obj)

        with self.captureOnCommitCallbacks(execute=True):
            obj.delete()

        self.assertFalse(path.exists())

    def test_purge_drops_expired_tickets_and_their_files(self):
        stale = self.ticket()
        self.put(stale)
        path = self.path(stale)

        with self.captureOnCommitCallbacks(execute=True):
            counts = services.purge(now=tz.now() + timedelta(days=1))

        self.assertEqual(counts["tickets"], 1)
        self.assertFalse(StoredObject.objects.filter(pk=stale.pk).exists())
        self.assertFalse(path.exists())


class BucketStorageTests(SimpleTestCase):
    """Only the links: building them needs no network."""

    options = {
        "endpoint_url": "https://storage.example.com",
        "region_name": "auto",
        "access_key": "key",
        "secret_key": "secret",
    }

    def obj(self):
        return StoredObject(
            key="todos/comments/ab.png",
            content_type="image/png",
            size=123,
            expires_at=tz.now() + timedelta(minutes=30),
        )

    def test_the_upload_link_pins_size_type_and_write_once(self):
        storage = BucketStorage(bucket_name="private", **self.options)

        url = storage.upload_url(self.obj())

        self.assertTrue(url.startswith(f"{self.options['endpoint_url']}/private/todos/comments/"))
        signed = parse_qs(urlsplit(url).query)["X-Amz-SignedHeaders"][0].split(";")
        self.assertEqual(set(signed), {"content-length", "content-type", "host", "if-none-match"})

    def test_public_files_come_from_the_custom_domain(self):
        storage = BucketStorage(
            bucket_name="public",
            custom_domain="s1.example.com",
            querystring_auth=False,
            **self.options,
        )

        self.assertTrue(storage.public)
        self.assertEqual(
            storage.object_url(self.obj(), timedelta(hours=1)),
            "https://s1.example.com/todos/comments/ab.png",
        )

    def test_private_files_get_presigned_links(self):
        storage = BucketStorage(bucket_name="private", **self.options)

        url = storage.object_url(self.obj(), timedelta(hours=1))

        self.assertFalse(storage.public)
        self.assertIn("X-Amz-Expires=3600", url)
