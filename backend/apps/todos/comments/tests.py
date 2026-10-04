from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone as tz

from apps.common.testing import PlatformTestCase
from apps.messaging.models import EmailMessage
from apps.profiles.models import Profile
from apps.storage.models import ObjectStatus, ObjectVisibility, StoredObject
from apps.todos.comments.models import Comment
from apps.todos.projects.models import Project
from apps.todos.tasks.models import Task

User = get_user_model()


@mock.patch("apps.messaging.models.Message.enqueue")
class CommentTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.authenticate()
        self.home = Project.objects.create(owner=self.user, name="Home")
        self.other = User.objects.create_user(email="other@example.com")
        Profile.objects.create(user=self.other, display_name="Other")
        self.home.join(self.other)
        self.task = Task.objects.create(project=self.home, content="Shop", created_by=self.user)

    def comment(self, text="Milk?", user=None, **target):
        self.authenticate(user or self.user)
        response = self.client.post(
            reverse("todo-comment-list"), {"task": self.task.pk, "text": text, **target}
        )
        self.authenticate(self.user)
        return response

    def upload(self, user=None):
        return StoredObject.objects.create(
            owner=user or self.user,
            content_type="image/png",
            max_size=100,
            size=100,
            status=ObjectStatus.READY,
            visibility=ObjectVisibility.PRIVATE,
            expires_at=tz.now(),
            extra={"purpose": "todos_comment", "name": "list.png"},
        )

    def test_comments_list_oldest_first_and_count_on_the_task(self, _enqueue):
        self.comment("One")
        self.comment("Two", user=self.other)

        listed = self.client.get(reverse("todo-comment-list"), {"task": self.task.pk}).data

        self.assertEqual([c["text"] for c in listed], ["One", "Two"])
        self.assertEqual(listed[1]["author"]["name"], "Other")
        task = self.client.get(reverse("todo-task-detail", args=[self.task.pk])).data
        self.assertEqual(task["comment_count"], 2)

    def test_project_comments(self, _enqueue):
        response = self.client.post(
            reverse("todo-comment-list"), {"project": self.home.pk, "text": "Notes"}
        )

        self.assertEqual(response.status_code, 201)
        listed = self.client.get(reverse("todo-comment-list"), {"project": self.home.pk}).data
        self.assertEqual([c["text"] for c in listed], ["Notes"])

    def test_a_comment_is_on_one_thing(self, _enqueue):
        response = self.comment(project=self.home.pk)

        self.assertEqual(response.status_code, 400)

    def test_others_cannot_see_or_comment(self, _enqueue):
        self.comment()
        stranger = User.objects.create_user(email="stranger@example.com")

        self.assertEqual(self.comment(user=stranger).status_code, 400)
        self.authenticate(stranger)
        listed = self.client.get(reverse("todo-comment-list"), {"task": self.task.pk}).data
        self.assertEqual(listed, [])

    def test_only_the_author_edits_and_the_owner_also_deletes(self, _enqueue):
        mine = self.comment().data["id"]
        theirs = self.comment("Eggs", user=self.other).data["id"]

        response = self.client.patch(reverse("todo-comment-detail", args=[theirs]), {"text": "x"})
        self.assertEqual(response.status_code, 403)
        response = self.client.patch(reverse("todo-comment-detail", args=[mine]), {"text": "Oat"})
        self.assertIsNotNone(response.data["edited_at"])
        self.authenticate(self.other)
        self.assertEqual(
            self.client.delete(reverse("todo-comment-detail", args=[mine])).status_code, 403
        )
        self.authenticate(self.user)
        self.assertEqual(
            self.client.delete(reverse("todo-comment-detail", args=[theirs])).status_code, 204
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.comment_count, 1)

    def test_attachments(self, _enqueue):
        obj = self.upload()

        response = self.comment("", attachment_id=obj.pk)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["attachment"]["name"], "list.png")
        self.assertIn("signature=", response.data["attachment"]["url"])
        # A file goes on one comment only, and only its uploader's.
        self.assertEqual(self.comment("again", attachment_id=obj.pk).status_code, 400)
        theirs = self.upload(self.other)
        self.assertEqual(self.comment("x", attachment_id=theirs.pk).status_code, 400)
        # Deleting the comment deletes the file.
        self.client.delete(reverse("todo-comment-detail", args=[response.data["id"]]))
        self.assertFalse(StoredObject.objects.filter(pk=obj.pk).exists())

    def test_an_empty_comment_is_refused(self, _enqueue):
        self.assertEqual(self.comment("  ").status_code, 400)

    def test_attachment_tickets_respect_the_limits(self, _enqueue):
        url = reverse("todo-comment-attachments")
        body = {"name": "a.pdf", "content_type": "application/pdf", "size": 1000}

        response = self.client.post(url, body)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["upload_url"].startswith("/api/v1/storage/uploads/"))
        with override_settings(TODOS_COMMENTS_MAX_ATTACHMENT_BYTES=999):
            self.assertEqual(self.client.post(url, body).status_code, 400)
        with override_settings(TODOS_COMMENTS_MAX_STORAGE_BYTES=1500):
            self.assertEqual(self.client.post(url, body).status_code, 400)

    def test_comments_email_the_creator_and_assignee_grouped(self, _enqueue):
        third = User.objects.create_user(email="third@example.com")
        self.home.join(third)
        self.task.assignee = third
        self.task.save()

        self.comment("One", user=self.other)
        self.comment("Two", user=self.other)

        emails = EmailMessage.objects.filter(extra__purpose="todos_comments")
        self.assertEqual(sorted(e.to for e in emails), ["someone@example.com", "third@example.com"])
        body = emails.get(to="someone@example.com").body
        self.assertIn("One", body)
        self.assertIn("Two", body)
        self.assertGreater(emails[0].next_attempt_at, tz.now() + timedelta(minutes=4))

    def test_no_email_for_your_own_comment_or_once_opted_out(self, _enqueue):
        self.comment("Mine")
        Profile.objects.create(user=self.user, extra={"todos_comment_emails": "false"})
        self.comment("Theirs", user=self.other)

        self.assertFalse(EmailMessage.objects.exists())

    def test_project_comments_email_only_those_who_opted_in(self, _enqueue):
        Profile.objects.create(user=self.user, extra={"todos_project_comment_emails": "true"})
        self.authenticate(self.other)

        self.client.post(reverse("todo-comment-list"), {"project": self.home.pk, "text": "Hi"})

        self.assertEqual([e.to for e in EmailMessage.objects.all()], ["someone@example.com"])

    def test_deleting_the_task_deletes_its_comments(self, _enqueue):
        self.comment()

        self.task.delete()

        self.assertFalse(Comment.objects.exists())
