import logging
from datetime import timedelta

from django.apps import apps
from django.db import transaction
from django.tasks import task
from django.utils import timezone as tz

from apps.messaging.models import MessageStatus

logger = logging.getLogger(__name__)

# Wait before each retry; one attempt more than there are delays, then give up.
RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1


@task
def send_message(model_label: str, message_id: str) -> str | None:
    """Make one attempt at sending a message; returns its status afterwards.

    Does nothing (returns None) if the message is no longer pending, so a task
    that runs twice never sends twice.
    """
    # Claim it: mark it sending and count the attempt.
    with transaction.atomic():
        message = (
            apps.get_model(model_label)
            .objects.select_for_update(skip_locked=True)
            .filter(pk=message_id, status=MessageStatus.PENDING)
            .first()
        )
        if message is None:
            return None
        message.status = MessageStatus.SENDING
        message.attempts += 1
        message.save(update_fields=("status", "attempts", "updated_at"))

    try:
        message.send()
    except Exception as exc:
        logger.warning("Message %s attempt %s failed", message.id, message.attempts, exc_info=True)
        message.last_error = f"{type(exc).__name__}: {exc}"
        if message.attempts >= MAX_ATTEMPTS:
            message.status = MessageStatus.FAILED
        else:
            message.status = MessageStatus.PENDING
            message.next_attempt_at = tz.now() + RETRY_DELAYS[message.attempts - 1]
    else:
        message.status = MessageStatus.SENT
        message.sent_at = tz.now()
        message.last_error = ""
    message.save(update_fields=("status", "next_attempt_at", "sent_at", "last_error", "updated_at"))
    if message.status == MessageStatus.PENDING:
        message.enqueue()
    return message.status
