import io
import json
from datetime import date, datetime, timedelta
from unittest import mock

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import override_settings
from django.urls import reverse
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response as HttpResponse

from apps.common.testing import PlatformTestCase
from apps.reminders.models import Reminder
from apps.todos.google.models import Connection, Push, event_id
from apps.todos.google.views import STATE_SALT
from apps.todos.projects.models import Project
from apps.todos.tasks.models import Task

User = get_user_model()
KEY = Fernet.generate_key().decode()


def not_found():
    return HttpError(HttpResponse({"status": 404}), b"")


@override_settings(TODOS_GOOGLE_ENCRYPTION_KEY=KEY)
class GoogleTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.authenticate()
        self.google = mock.MagicMock()
        patcher = mock.patch.object(Connection, "service", return_value=self.google)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.home = Project.objects.create(owner=self.user, name="Home")

    def connected(self, **fields):
        return Connection.objects.create(
            user=self.user,
            refresh_token=Fernet(KEY.encode()).encrypt(b"refresh"),
            calendar_id="cal",
            **fields,
        )

    def test_connecting_makes_the_calendar_watches_it_and_sends_dated_tasks(self):
        Task.objects.create(project=self.home, content="Dated", due_date=date(2026, 10, 5))
        self.google.calendars().insert().execute.return_value = {"id": "cal"}
        self.google.events().watch().execute.return_value = {
            "resourceId": "r",
            "expiration": "1893456000000",
        }
        self.google.events().list().execute.return_value = {"items": [], "nextSyncToken": "t"}
        state = signing.dumps(str(self.user.pk), salt=STATE_SALT)
        token = io.BytesIO(json.dumps({"refresh_token": "refresh"}).encode())

        with mock.patch("urllib.request.urlopen", return_value=token):
            response = self.client.get(
                reverse("todo-google-callback"), {"code": "c", "state": state}
            )

        self.assertEqual(response.status_code, 200, response.data)
        connection = Connection.objects.get(user=self.user)
        self.assertEqual((connection.calendar_id, connection.sync_token), ("cal", "t"))
        self.assertNotIn(b"refresh", bytes(connection.refresh_token))
        self.assertEqual(connection.token(), "refresh")
        self.assertEqual(connection.pushes.count(), 1)
        self.assertTrue(
            Reminder.objects.filter(object_id=connection.pk, rule__contains="15").exists()
        )

    def test_a_forged_state_is_refused(self):
        response = self.client.get(reverse("todo-google-callback"), {"code": "c", "state": "x"})

        self.assertEqual(response.status_code, 400)

    def test_timed_and_all_day_events(self):
        connection = self.connected()
        timed = Task.objects.create(
            project=self.home,
            content="Call",
            due_date=date(2026, 10, 5),
            due_at=datetime.fromisoformat("2026-10-05T09:00:00+00:00"),
        )
        day = Task.objects.create(project=self.home, content="Shop", due_date=date(2026, 10, 5))

        self.assertEqual(connection.event(timed)["end"]["dateTime"], "2026-10-05T09:30:00+00:00")
        self.assertEqual(connection.event(day)["start"], {"date": "2026-10-05"})
        self.assertEqual(connection.event(day)["end"], {"date": "2026-10-06"})
        self.assertEqual(connection.event(day)["id"], day.pk.hex)

    def test_saving_a_task_queues_a_push_and_pushing_updates_or_inserts(self):
        connection = self.connected()
        task = Task.objects.create(project=self.home, content="Shop", due_date=date(2026, 10, 5))
        self.assertEqual(list(connection.pushes.values_list("task_id", flat=True)), [task.pk])
        self.google.events().update().execute.side_effect = not_found()

        connection.push_pending()

        self.google.events().insert.assert_called_with(
            calendarId="cal", body=connection.event(task)
        )
        self.assertFalse(connection.pushes.exists())

    def test_completing_or_undating_removes_the_event(self):
        connection = self.connected()
        task = Task.objects.create(project=self.home, content="Shop", due_date=date(2026, 10, 5))
        connection.pushes.all().delete()

        task.close()
        connection.push_pending()

        self.google.events().delete.assert_called_with(calendarId="cal", eventId=event_id(task.pk))

    def test_a_failed_push_waits_and_a_revoked_token_disconnects(self):
        connection = self.connected()
        Task.objects.create(project=self.home, content="Shop", due_date=date(2026, 10, 5))
        self.google.events().update().execute.side_effect = HttpError(
            HttpResponse({"status": 500}), b""
        )

        connection.push_pending()

        push = Push.objects.get()
        self.assertEqual(push.attempts, 1)
        push.next_attempt_at = push.next_attempt_at - timedelta(hours=1)
        push.save()
        self.google.events().update().execute.side_effect = RefreshError("revoked")
        connection.push_pending()
        connection.refresh_from_db()
        self.assertEqual(connection.status, "disconnected")
        self.assertEqual(self.client.get(reverse("todo-google")).data["status"], "disconnected")

    def test_only_chosen_projects_and_shared_tasks_assigned_to_me(self):
        connection = self.connected(projects=[])
        other = User.objects.create_user(email="other@example.com")
        theirs = Project.objects.create(owner=other, name="Theirs")
        theirs.join(self.user)
        mine = Task.objects.create(project=self.home, content="Mine", due_date=date(2026, 10, 5))
        assigned = Task.objects.create(
            project=theirs, content="Assigned", assignee=self.user, due_date=date(2026, 10, 5)
        )
        Task.objects.create(project=theirs, content="Not mine", due_date=date(2026, 10, 5))

        self.assertEqual(list(connection.followed()), [assigned])
        connection.projects = None
        self.assertEqual(set(connection.followed()), {mine, assigned})

    def test_changes_in_google_move_rename_or_undate_the_task(self):
        connection = self.connected(sync_token="old")
        task = Task.objects.create(project=self.home, content="Shop", due_date=date(2026, 10, 5))
        undated = Task.objects.create(project=self.home, content="Call", due_date=date(2026, 10, 5))
        self.google.events().list().execute.return_value = {
            "items": [
                {"id": task.pk.hex, "summary": "Shop for food", "start": {"date": "2026-10-07"}},
                {"id": undated.pk.hex, "status": "cancelled"},
                {"id": "notatask", "summary": "x"},
            ],
            "nextSyncToken": "new",
        }

        connection.pull()

        task.refresh_from_db()
        undated.refresh_from_db()
        self.assertEqual((task.content, task.due_date), ("Shop for food", date(2026, 10, 7)))
        self.assertIsNone(undated.due_date)
        self.assertTrue(Task.objects.filter(pk=undated.pk).exists())
        connection.refresh_from_db()
        self.assertEqual(connection.sync_token, "new")

    def test_the_webhook_checks_the_channel_token(self):
        self.connected(channel_id="chan", channel_token="secret")
        url = reverse("todo-google-webhook")

        forged = self.client.post(url, HTTP_X_GOOG_CHANNEL_ID="chan", HTTP_X_GOOG_CHANNEL_TOKEN="x")
        self.assertEqual(forged.status_code, 404)
        with mock.patch("apps.todos.google.views.pull_changes") as pull:
            response = self.client.post(
                url,
                HTTP_X_GOOG_CHANNEL_ID="chan",
                HTTP_X_GOOG_CHANNEL_TOKEN="secret",
                HTTP_X_GOOG_RESOURCE_STATE="exists",
            )
        self.assertEqual(response.status_code, 204)
        pull.enqueue.assert_called_once()

    def test_choosing_projects_and_disconnecting(self):
        connection = self.connected()
        Task.objects.create(project=self.home, content="Shop", due_date=date(2026, 10, 5))

        response = self.client.patch(
            reverse("todo-google"), {"projects": [str(self.home.pk)]}, format="json"
        )
        self.assertEqual(response.data["projects"], [str(self.home.pk)])

        with mock.patch("urllib.request.urlopen"):
            self.assertEqual(self.client.delete(reverse("todo-google")).status_code, 204)
        self.google.calendars().delete.assert_called_with(calendarId="cal")
        self.assertFalse(Connection.objects.filter(pk=connection.pk).exists())
