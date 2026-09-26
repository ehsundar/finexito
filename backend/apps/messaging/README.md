# messaging

Outgoing messages, sent in the background and kept as a ledger. Every send is a
row that says where it stands. `Message` is an abstract base with the ledger
fields; each channel is a concrete model (its own table) with the content and a
`send()` method. Email is the only channel so far.

## Sending

Create the message; that is all:

```python
from apps.messaging.models import EmailMessage

EmailMessage.objects.create(
    to="someone@example.com",
    subject="…",
    body="plain text",
    html_body="<p>optional</p>",
    extra={"purpose": "welcome"},
)
```

Saving a new message queues a `send_message(model_label, id)` task once the
transaction commits; `manage.py db_worker` (the `worker` container, from
django-tasks-db) runs it. A rolled-back transaction leaves neither the row nor
the task behind. `bulk_create` skips `save()`, so it queues nothing.

## Lifecycle

`pending` → `sending` → `sent`. When an attempt raises, the message goes back to
`pending` and a new task is queued to run after a delay (1 min, 5 min, 30 min,
2 h); after the fifth attempt it is `failed`. The task only acts on a `pending`
message, so a task that runs twice never sends twice. Admins can retry failed
messages from the admin, which queues a fresh task.

A worker killed mid-send leaves that message `sending`; nothing picks it up
again, so look for such rows in the admin.

## Adding a channel

1. A subclass of `Message` with the content fields and a `send()` that raises
   on failure (`class Meta(Message.Meta)` keeps the ordering).
2. An admin subclassing `MessageAdmin`.
