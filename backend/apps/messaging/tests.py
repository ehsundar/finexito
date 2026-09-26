from unittest import mock

from django.core import mail
from django.test import TestCase
from django.utils import timezone as tz
from django_tasks_db.models import DBTaskResult

from apps.messaging.admin import retry
from apps.messaging.models import EmailMessage, MessageStatus
from apps.messaging.tasks import MAX_ATTEMPTS, send_message

SEND = "django.core.mail.EmailMultiAlternatives.send"


class MessagingTestCase(TestCase):
    def queue_email(self, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            return EmailMessage.objects.create(
                to="someone@example.com", subject="Hello", body="Plain", **kwargs
            )

    def run_task(self, message):
        """Run the message's task inline, collecting the retry it may queue."""
        with self.captureOnCommitCallbacks(execute=True):
            return send_message.call(message._meta.label, str(message.pk))

    def queued(self):
        return DBTaskResult.objects.filter(task_path=send_message.module_path)


class CreateTests(MessagingTestCase):
    def test_creating_a_message_queues_its_task(self):
        message = self.queue_email()

        self.assertEqual(message.status, MessageStatus.PENDING)
        task = self.queued().get()
        self.assertEqual(task.args_kwargs["args"], ["messaging.EmailMessage", str(message.pk)])
        self.assertEqual(mail.outbox, [])

    def test_nothing_is_queued_if_the_transaction_rolls_back(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            EmailMessage.objects.create(to="someone@example.com", subject="Hello", body="Plain")

        self.assertEqual(len(callbacks), 1)
        self.assertFalse(self.queued().exists())


class SendMessageTaskTests(MessagingTestCase):
    def test_sends_the_message_and_marks_it_sent(self):
        message = self.queue_email(html_body="<p>Rich</p>")

        self.assertEqual(self.run_task(message), MessageStatus.SENT)

        message.refresh_from_db()
        self.assertEqual(message.attempts, 1)
        self.assertIsNotNone(message.sent_at)
        self.assertEqual(mail.outbox[0].to, ["someone@example.com"])
        self.assertEqual(mail.outbox[0].alternatives[0].content, "<p>Rich</p>")

    def test_saving_an_existing_message_queues_nothing_more(self):
        message = self.queue_email()

        with self.captureOnCommitCallbacks(execute=True):
            message.save()

        self.assertEqual(self.queued().count(), 1)

    def test_running_twice_sends_once(self):
        message = self.queue_email()

        self.run_task(message)

        self.assertIsNone(self.run_task(message))
        self.assertEqual(len(mail.outbox), 1)

    def test_a_failed_send_queues_a_later_retry(self):
        message = self.queue_email()

        with mock.patch(SEND, side_effect=TimeoutError("timed out")):
            self.run_task(message)

        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.PENDING)
        self.assertIn("timed out", message.last_error)
        self.assertGreater(message.next_attempt_at, tz.now())
        retry = self.queued().order_by("-enqueued_at").first()
        self.assertEqual(retry.run_after, message.next_attempt_at)

    def test_gives_up_after_the_last_attempt(self):
        message = self.queue_email()

        with mock.patch(SEND, side_effect=TimeoutError("timed out")):
            for _ in range(MAX_ATTEMPTS):
                self.run_task(message)

        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.FAILED)
        self.assertEqual(message.attempts, MAX_ATTEMPTS)
        self.assertEqual(self.queued().count(), MAX_ATTEMPTS)

    def test_retry_gives_a_failed_message_another_go(self):
        message = self.queue_email()
        EmailMessage.objects.filter(pk=message.pk).update(
            status=MessageStatus.FAILED, attempts=MAX_ATTEMPTS
        )

        with self.captureOnCommitCallbacks(execute=True):
            retry(mock.Mock(), None, EmailMessage.objects.all())

        self.assertEqual(self.queued().count(), 2)
        self.assertEqual(self.run_task(message), MessageStatus.SENT)
