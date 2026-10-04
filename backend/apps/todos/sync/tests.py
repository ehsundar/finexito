import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone as tz

from apps.common.testing import PlatformTestCase
from apps.todos.projects.models import Project
from apps.todos.sync.models import Tombstone
from apps.todos.tasks.models import Task

User = get_user_model()


class SyncTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.authenticate()
        self.home = Project.objects.create(owner=self.user, name="Home")

    def pull(self, since=None):
        params = {"since": since} if since else {}
        return self.client.get(reverse("todo-sync"), params).data

    def push(self, *ops):
        return self.client.post(reverse("todo-sync"), {"operations": list(ops)}, format="json")

    def op(self, method, path, body=None, id=None):
        return {"id": str(id or uuid.uuid4()), "method": method, "path": path, "body": body or {}}

    def test_a_full_load_then_only_changes(self):
        earlier = tz.now() - timedelta(minutes=2)
        with mock.patch("django.utils.timezone.now", lambda: earlier):
            Task.objects.create(project=self.home, content="Old")
        with mock.patch("django.utils.timezone.now", lambda: earlier + timedelta(minutes=1)):
            first = self.pull()
        self.assertTrue(first["full"])
        self.assertEqual([t["content"] for t in first["tasks"]], ["Old"])

        later = tz.now() + timedelta(seconds=10)
        with mock.patch("django.utils.timezone.now", lambda: later):
            Task.objects.create(project=self.home, content="New")
        changes = self.pull(first["token"])

        self.assertFalse(changes["full"])
        self.assertEqual([t["content"] for t in changes["tasks"]], ["New"])

    def test_deletions_reach_everyone_who_could_see_them(self):
        other = User.objects.create_user(email="other@example.com")
        self.home.join(other)
        task = Task.objects.create(project=self.home, content="Gone")
        task_id, home_id = task.pk, self.home.pk
        token = (tz.now() - timedelta(seconds=1)).isoformat()

        task.delete()

        self.authenticate(other)
        self.assertEqual(self.pull(token)["deleted"], [{"kind": "task", "id": task_id}])
        self.home.delete()
        self.assertIn({"kind": "project", "id": home_id}, self.pull(token)["deleted"])

    def test_leaving_sends_the_project_as_deleted(self):
        other = User.objects.create_user(email="other@example.com")
        self.home.join(other)
        token = (tz.now() - timedelta(seconds=1)).isoformat()

        self.home.remove(other)

        self.authenticate(other)
        self.assertEqual(self.pull(token)["deleted"], [{"kind": "project", "id": self.home.pk}])

    def test_joining_sends_the_whole_project(self):
        Task.objects.create(project=self.home, content="Before")
        other = User.objects.create_user(email="other@example.com")
        self.authenticate(other)
        token = self.pull()["token"]

        later = tz.now() + timedelta(seconds=10)
        with mock.patch("django.utils.timezone.now", lambda: later):
            self.home.join(other)
        changes = self.pull(token)

        self.assertEqual([p["name"] for p in changes["projects"]], ["Home"])
        self.assertEqual([t["content"] for t in changes["tasks"]], ["Before"])

    def test_an_old_token_gets_everything(self):
        old = (tz.now() - timedelta(days=31)).isoformat()

        self.assertTrue(self.pull(old)["full"])

    def test_queued_operations_apply_in_order_with_client_ids(self):
        project, task = uuid.uuid4(), uuid.uuid4()

        response = self.push(
            self.op("POST", "/api/v1/todos/projects/", {"id": str(project), "name": "Trip"}),
            self.op(
                "POST",
                "/api/v1/todos/tasks/",
                {"id": str(task), "project": str(project), "content": "Pack"},
            ),
            self.op("POST", f"/api/v1/todos/tasks/{task}/close/"),
        )

        self.assertEqual([r["status"] for r in response.data], [201, 201, 200])
        self.assertIsNotNone(Task.objects.get(pk=task, project_id=project).completed_at)

    def test_sending_an_operation_twice_applies_it_once(self):
        op = self.op(
            "POST", "/api/v1/todos/tasks/", {"project": str(self.home.pk), "content": "Once"}
        )

        self.push(op)
        response = self.push(op)

        self.assertEqual(response.data[0]["body"], None)
        self.assertEqual(Task.objects.filter(content="Once").count(), 1)

    def test_a_refused_operation_reports_and_the_rest_go_on(self):
        theirs = Project.objects.create(
            owner=User.objects.create_user(email="x@example.com"), name="X"
        )

        response = self.push(
            self.op("POST", "/api/v1/todos/tasks/", {"project": str(theirs.pk), "content": "No"}),
            self.op(
                "POST", "/api/v1/todos/tasks/", {"project": str(self.home.pk), "content": "Yes"}
            ),
            self.op("POST", "/api/v1/auth/logout/"),
        )

        self.assertEqual([r["status"] for r in response.data], [400, 201, 400])
        self.assertFalse(Task.objects.filter(content="No").exists())

    def test_an_edit_to_a_deleted_task_is_not_found(self):
        task = Task.objects.create(project=self.home, content="Gone")
        task_id = task.pk
        task.delete()

        response = self.push(self.op("PATCH", f"/api/v1/todos/tasks/{task_id}/", {"content": "x"}))

        self.assertEqual(response.data[0]["status"], 404)

    def test_a_taken_id_is_refused(self):
        response = self.push(
            self.op("POST", "/api/v1/todos/projects/", {"id": str(self.home.pk), "name": "Steal"})
        )

        self.assertEqual(response.data[0]["status"], 400)
        self.home.refresh_from_db()
        self.assertEqual(self.home.name, "Home")

    def test_completing_a_recurring_task_twice_advances_it_twice(self):
        task = Task.objects.create(project=self.home, content="Water", due_date=tz.now().date())
        self.client.patch(reverse("todo-task-detail", args=[task.pk]), {"due_string": "every day"})
        task.refresh_from_db()
        start = task.due_date

        self.push(
            self.op("POST", f"/api/v1/todos/tasks/{task.pk}/close/"),
            self.op("POST", f"/api/v1/todos/tasks/{task.pk}/close/"),
        )

        task.refresh_from_db()
        self.assertEqual(task.due_date, start + timedelta(days=2))
        self.assertEqual(Tombstone.objects.count(), 0)
