import io
import shutil
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone as tz

from apps.common.testing import PlatformTestCase
from apps.storage import services
from apps.storage.models import ObjectStatus, ObjectVisibility, StoredObject

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
        defaults = {"content_type": "image/png", "max_size": 1000}
        return services.create_upload(self.user, **{**defaults, **fields})

    def put(self, obj, body=PNG, content_type="image/png", **headers):
        return self.client.generic(
            "PUT", services.upload_url(obj), body, content_type=content_type, **headers
        )


class CreateUploadTests(StorageTestCase):
    def test_refuses_types_a_browser_could_run(self):
        for content_type in ("image/svg+xml", "text/html", "application/javascript"):
            with self.subTest(content_type), self.assertRaises(ValueError):
                self.ticket(content_type=content_type)

    @override_settings(STORAGE_MAX_UPLOAD_BYTES=500)
    def test_refuses_sizes_over_the_global_limit(self):
        with self.assertRaises(ValueError):
            self.ticket(max_size=501)


class UploadTests(StorageTestCase):
    def test_the_owner_uploads_and_gets_a_public_url(self):
        obj = self.ticket()
        self.authenticate()

        response = self.put(obj)

        self.assertEqual(response.status_code, 200, response.data)
        obj.refresh_from_db()
        self.assertEqual((obj.status, obj.size), (ObjectStatus.READY, len(PNG)))
        self.assertEqual(obj.path.read_bytes(), PNG)
        self.assertEqual(obj.path, self.root / "public" / obj.key)
        self.assertEqual(response.data["url"], f"/api/media/{obj.key}")
        self.assertEqual(list((self.root / "tmp").iterdir()), [])

    def test_anyone_else_gets_a_404(self):
        obj = self.ticket()
        self.authenticate(User.objects.create_user(email="other@example.com", password="x"))

        self.assertEqual(self.put(obj).status_code, 404)

    def test_anonymous_callers_are_refused(self):
        self.assertEqual(self.put(self.ticket()).status_code, 401)

    def test_refusals(self):
        self.authenticate()
        cases = [
            ("wrong type", {"content_type": "image/jpeg"}, 415),
            ("too large", {"body": PNG + b"\x00" * 1000}, 413),
            ("not really a png", {"body": b"<html><script>alert(1)</script>"}, 415),
        ]
        for name, kwargs, code in cases:
            with self.subTest(name):
                obj = self.ticket()
                response = self.put(obj, **kwargs)
                self.assertEqual(response.status_code, code, response.data)
                obj.refresh_from_db()
                self.assertEqual(obj.status, ObjectStatus.PENDING)
                self.assertFalse(obj.path.exists())

    def test_a_body_shorter_than_its_content_length_is_refused(self):
        obj = self.ticket()

        with self.assertRaises(services.UploadError):
            services.receive_upload(
                obj, self.user, io.BytesIO(PNG), content_type="image/png", length=len(PNG) + 10
            )

        obj.refresh_from_db()
        self.assertEqual(obj.status, ObjectStatus.PENDING)
        self.assertFalse(obj.path.exists())
        self.assertEqual(list((self.root / "tmp").iterdir()), [])

    def test_an_empty_body_is_refused(self):
        with self.assertRaises(services.UploadError):
            services.receive_upload(
                self.ticket(), self.user, io.BytesIO(), content_type="image/png", length=0
            )

    def test_an_object_uploads_only_once(self):
        self.authenticate()
        obj = self.ticket()
        self.put(obj)

        self.assertEqual(self.put(obj).status_code, 409)

    def test_an_expired_ticket_is_refused(self):
        self.authenticate()
        obj = self.ticket(ttl=timedelta(seconds=-1))

        self.assertEqual(self.put(obj).status_code, 410)


class PrivateObjectTests(StorageTestCase):
    def setUp(self):
        super().setUp()
        self.obj = self.ticket(visibility=ObjectVisibility.PRIVATE)
        self.authenticate()
        self.put(self.obj)
        self.obj.refresh_from_db()
        self.client.force_authenticate(None)

    def test_lands_outside_the_public_directory(self):
        self.assertEqual(self.obj.path, self.root / "private" / self.obj.key)

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
        expired = int(time.time()) - 1
        for name, link in (
            ("tampered", url[:-1] + ("A" if url[-1] != "A" else "B")),
            ("unsigned", url.split("?")[0]),
            (
                "expired",
                f"{url.split('?')[0]}?expires={expired}"
                f"&signature={services._signature(self.obj, expired)}",
            ),
        ):
            with self.subTest(name):
                self.assertEqual(self.client.get(link).status_code, 404)


class HousekeepingTests(StorageTestCase):
    def test_deleting_a_row_deletes_its_file(self):
        obj = self.ticket()
        self.authenticate()
        self.put(obj)
        path = obj.path

        with self.captureOnCommitCallbacks(execute=True):
            obj.delete()

        self.assertFalse(path.exists())

    def test_purge_drops_expired_tickets_and_orphans(self):
        stale = self.ticket(ttl=timedelta(seconds=-1))
        live = self.ticket()
        orphan = self.root / "public" / "ab" / "ab000000000000000000000000000000.png"
        orphan.parent.mkdir(parents=True)
        orphan.write_bytes(PNG)

        counts = services.purge(now=tz.now() + timedelta(days=1))

        self.assertFalse(StoredObject.objects.filter(pk=stale.pk).exists())
        self.assertEqual(counts["orphans"], 1)
        self.assertFalse(orphan.exists())
        self.assertFalse(StoredObject.objects.filter(pk=live.pk).exists())  # expired by then too
