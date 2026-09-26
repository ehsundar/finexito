"""The outgoing message ledger: one table per channel, all sharing Message's fields."""

from django.core import mail
from django.db import models, transaction
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel


class MessageStatus(models.TextChoices):
    PENDING = "pending", _("Waiting to be sent")
    SENDING = "sending", _("Being sent")
    SENT = "sent", _("Handed to the provider")
    FAILED = "failed", _("Gave up after the last attempt")


class Message(BaseModel):
    """What every channel shares: where a send stands and how its attempts went.

    Each channel is a concrete subclass holding the content and knowing how to
    hand it to its provider. Creating one is all it takes to send it: saving a
    new message queues its send (bulk_create skips save(), so it queues nothing).
    """

    status = models.CharField(max_length=20, choices=MessageStatus, default=MessageStatus.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=tz.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        abstract = True
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self._meta.verbose_name} {self.id} ({self.status})"

    def save(self, *args, **kwargs):
        adding = self._state.adding
        super().save(*args, **kwargs)
        if adding and self.status == MessageStatus.PENDING:
            self.enqueue()

    def retry(self) -> None:
        """Give the message a fresh run of attempts, starting now."""
        self.status = MessageStatus.PENDING
        self.attempts = 0
        self.next_attempt_at = tz.now()
        self.save(update_fields=("status", "attempts", "next_attempt_at", "updated_at"))
        self.enqueue()

    def enqueue(self) -> None:
        """Queue an attempt at next_attempt_at, once the transaction commits.

        After commit, so the worker can see the row, and a rollback queues nothing.
        """
        # Imported here: the task module imports this one.
        from apps.messaging.tasks import send_message

        task = send_message.using(run_after=self.next_attempt_at)
        label, pk = self._meta.label, str(self.pk)
        transaction.on_commit(lambda: task.enqueue(label, pk))

    def send(self) -> None:
        """Hand the message to the provider; raise to report a failed attempt."""
        raise NotImplementedError


class EmailMessage(Message):
    to = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text=_("Plain text; always sent."))
    html_body = models.TextField(blank=True, help_text=_("Sent alongside the text if set."))
    from_email = models.CharField(
        max_length=255, blank=True, help_text=_("Blank for DEFAULT_FROM_EMAIL.")
    )

    class Meta(Message.Meta):
        verbose_name = _("email message")
        verbose_name_plural = _("email messages")

    def send(self) -> None:
        email = mail.EmailMultiAlternatives(
            subject=self.subject,
            body=self.body,
            from_email=self.from_email or None,
            to=[self.to],
        )
        if self.html_body:
            email.attach_alternative(self.html_body, "text/html")
        email.send()
