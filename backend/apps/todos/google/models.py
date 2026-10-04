"""Dated tasks in a member's Google Calendar, and changes there back in the tasks.

A ``Connection`` is one member's consent: a refresh token (encrypted), the
calendar the app made for them, and the watch channel Google notifies of
changes. Each dated task they follow is one event, whose id is the task's id in
hex (a valid Google event id), so nothing else links the two.

Changes go to Google after they commit, through ``Push`` rows that a background
task works off; a failed push stays and is retried by the connection's reminder
(the reminders cron), which also renews the channel before it expires.
"""

import json
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, date, datetime, timedelta

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.tasks import task as background
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from apps.common.models import BaseModel
from apps.reminders.models import Reminder, reminder_due, zone
from apps.todos.projects.models import Project, member_left
from apps.todos.tasks.models import Task, member_zone, tasks_changed

SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
# How often the connection's reminder retries pushes and checks the channel.
CHECK_RULE = "FREQ=MINUTELY;INTERVAL=15"


def fernet() -> Fernet:
    return Fernet(settings.TODOS_GOOGLE_ENCRYPTION_KEY.encode())


def redirect_uri() -> str:
    return f"{settings.PUBLIC_ORIGIN}/todos/google"


def event_id(task_id) -> str:
    return uuid.UUID(str(task_id)).hex


class ConnectionStatus(models.TextChoices):
    CONNECTED = "connected", _("Connected")
    DISCONNECTED = "disconnected", _("Disconnected (access was revoked)")


class Connection(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todo_google"
    )
    status = models.CharField(
        max_length=20, choices=ConnectionStatus, default=ConnectionStatus.CONNECTED
    )
    refresh_token = models.BinaryField(editable=False, help_text=_("Encrypted."))
    calendar_id = models.CharField(max_length=255, blank=True, editable=False)
    # Null: all the member's own projects. Shared projects' tasks assigned to
    # them come along either way.
    projects = models.JSONField(null=True, blank=True)
    channel_id = models.CharField(max_length=64, blank=True, editable=False)
    channel_token = models.CharField(max_length=64, blank=True, editable=False)
    channel_resource = models.CharField(max_length=255, blank=True, editable=False)
    channel_expires_at = models.DateTimeField(null=True, blank=True, editable=False)
    sync_token = models.TextField(blank=True, editable=False)
    last_synced_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_error = models.TextField(blank=True, editable=False)
    reminders = GenericRelation(Reminder)

    class Meta(BaseModel.Meta):
        verbose_name = _("Google Calendar connection")
        verbose_name_plural = _("Google Calendar connections")

    def __str__(self) -> str:
        return f"{self.user} ({self.status})"

    # --- consent -------------------------------------------------------------

    @classmethod
    def consent_url(cls, user, state: str) -> str:
        query = urllib.parse.urlencode(
            {
                "client_id": settings.ACCOUNTS_GOOGLE_CLIENT_ID,
                "redirect_uri": redirect_uri(),
                "response_type": "code",
                "scope": SCOPE,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "login_hint": user.email,
                "state": state,
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    @classmethod
    def connect(cls, user, code: str) -> "Connection":
        """Trade the consent's code for a refresh token, make the calendar, start
        watching it, and send the member's dated tasks."""
        body = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": settings.ACCOUNTS_GOOGLE_CLIENT_ID,
                "client_secret": settings.ACCOUNTS_GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
            }
        ).encode()
        with urllib.request.urlopen(TOKEN_URL, data=body, timeout=10) as response:
            token = json.load(response)["refresh_token"]
        cls.objects.filter(user=user).delete()
        connection = cls(user=user, refresh_token=fernet().encrypt(token.encode()))
        calendar = (
            connection.service()
            .calendars()
            .insert(body={"summary": f"Tasks — {settings.SITE_NAME}"})
            .execute()
        )
        connection.calendar_id = calendar["id"]
        connection.save()
        connection.watch()
        Reminder.objects.create(
            user=user,
            target=connection,
            start_at=tz.now() + timedelta(minutes=15),
            rule=CHECK_RULE,
        )
        connection.queue(connection.followed())
        return connection

    def disconnect(self):
        """Delete the calendar, stop the channel, revoke the token; best effort, since
        the member may already have revoked it from Google's side."""
        if self.status == ConnectionStatus.CONNECTED:
            try:
                service = self.service()
                self.stop_channel(service)
                service.calendars().delete(calendarId=self.calendar_id).execute()
                token = urllib.parse.urlencode({"token": self.token()}).encode()
                urllib.request.urlopen(REVOKE_URL, data=token, timeout=10).close()
            except (HttpError, RefreshError, OSError):
                pass
        self.delete()

    # --- talking to Google ------------------------------------------------------

    def token(self) -> str:
        return fernet().decrypt(bytes(self.refresh_token)).decode()

    def service(self):
        credentials = Credentials(
            None,
            refresh_token=self.token(),
            token_uri=TOKEN_URL,
            client_id=settings.ACCOUNTS_GOOGLE_CLIENT_ID,
            client_secret=settings.ACCOUNTS_GOOGLE_CLIENT_SECRET,
            scopes=[SCOPE],
        )
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def revoked(self, error: RefreshError):
        """Google refused the token: the member revoked access from their side."""
        self.status, self.last_error = ConnectionStatus.DISCONNECTED, str(error)[:2000]
        self.save(update_fields=("status", "last_error", "updated_at"))

    def watch(self):
        """Ask Google to tell the webhook when the calendar changes (about a week)."""
        channel_id, token = uuid.uuid4().hex, uuid.uuid4().hex
        address = f"{settings.PUBLIC_ORIGIN}/api/v1/todos/google/webhook/"
        service = self.service()
        self.stop_channel(service)
        if not self.sync_token:
            self.pull(service)
        channel = (
            service.events()
            .watch(
                calendarId=self.calendar_id,
                body={"id": channel_id, "type": "web_hook", "address": address, "token": token},
            )
            .execute()
        )
        self.channel_id, self.channel_token = channel_id, token
        self.channel_resource = channel.get("resourceId", "")
        expires = int(channel.get("expiration", 0)) / 1000
        self.channel_expires_at = datetime.fromtimestamp(expires, UTC) if expires else None
        self.save()

    def stop_channel(self, service):
        if not self.channel_id:
            return
        try:
            body = {"id": self.channel_id, "resourceId": self.channel_resource}
            service.channels().stop(body=body).execute()
        except HttpError:
            pass

    # --- tasks to events ---------------------------------------------------------

    def followed(self):
        """The tasks this member's calendar shows, if they have a date."""
        own = Project.objects.filter(owner=self.user)
        if self.projects is not None:
            own = own.filter(pk__in=self.projects)
        assigned = Task.objects.filter(assignee=self.user).exclude(project__owner=self.user)
        return Task.objects.filter(
            models.Q(project__in=own) | models.Q(pk__in=assigned.values("pk"))
        ).filter(project__is_archived=False)

    def event(self, task: Task) -> dict:
        if task.due_at:
            end = task.due_at + timedelta(minutes=settings.TODOS_GOOGLE_EVENT_MINUTES)
            start, end = {"dateTime": task.due_at.isoformat()}, {"dateTime": end.isoformat()}
        else:
            start = {"date": task.due_date.isoformat()}
            end = {"date": (task.due_date + timedelta(days=1)).isoformat()}
        link = f"{settings.PUBLIC_ORIGIN}/todos/task?id={task.pk}"
        return {
            "id": event_id(task.pk),
            "summary": task.content,
            "description": f"{task.project.name}\n{link}",
            "start": start,
            "end": end,
        }

    def queue(self, tasks):
        """Note the tasks to push, and push them once this transaction commits."""
        ids = list(tasks.values_list("pk", flat=True)) if hasattr(tasks, "values_list") else tasks
        Push.objects.bulk_create(
            [Push(connection=self, task_id=pk) for pk in ids], ignore_conflicts=True
        )
        pk = str(self.pk)
        transaction.on_commit(lambda: push_pending.enqueue(pk))

    def push(self, service, task_id):
        """Make the event match the task: there if it's followed, open and dated."""
        task = self.followed().filter(pk=task_id).select_related("project").first()
        events = service.events()
        if task is None or task.completed_at or not task.due_date:
            try:
                events.delete(calendarId=self.calendar_id, eventId=event_id(task_id)).execute()
            except HttpError as error:
                if error.resp.status not in (404, 410):
                    raise
            return
        body = self.event(task)
        try:
            events.update(calendarId=self.calendar_id, eventId=body["id"], body=body).execute()
        except HttpError as error:
            if error.resp.status not in (404, 410):
                raise
            events.insert(calendarId=self.calendar_id, body=body).execute()

    def push_pending(self):
        """Push what's waiting; whatever fails waits for the next try."""
        if self.status != ConnectionStatus.CONNECTED:
            return
        pending = list(self.pushes.filter(next_attempt_at__lte=tz.now())[:500])
        if not pending:
            return
        service = self.service()
        for push in pending:
            try:
                self.push(service, push.task_id)
            except RefreshError as error:
                return self.revoked(error)
            except (HttpError, OSError) as error:
                push.attempts += 1
                push.last_error = str(error)[:2000]
                push.next_attempt_at = tz.now() + timedelta(minutes=5 * push.attempts)
                push.save()
                self.last_error = push.last_error
            else:
                push.delete()
        self.last_synced_at = tz.now()
        self.save(update_fields=("last_synced_at", "last_error", "updated_at"))

    # --- events back to tasks -------------------------------------------------------

    def pull(self, service=None):
        """Take in what changed in the calendar since the last sync token.

        A moved or renamed event moves or renames its task (a change of duration
        doesn't); a deleted one takes the task's date away, not the task.
        """
        service = service or self.service()
        page, changed = None, []
        while True:
            query = {"calendarId": self.calendar_id, "showDeleted": True, "pageToken": page}
            if self.sync_token:
                query["syncToken"] = self.sync_token
            try:
                result = service.events().list(**query).execute()
            except HttpError as error:
                if error.resp.status != 410 or not self.sync_token:
                    raise
                # The token's too old: start over from everything.
                self.sync_token = ""
                continue
            changed += result.get("items", [])
            page = result.get("nextPageToken")
            if not page:
                self.sync_token = result.get("nextSyncToken", "")
                break
        followed = self.followed()
        for event in changed:
            try:
                task = followed.filter(pk=uuid.UUID(event["id"])).first()
            except ValueError:
                continue
            if task is not None and not task.completed_at and task.due_date:
                self.take(task, event)
        self.last_synced_at = tz.now()
        self.save()

    def take(self, task: Task, event: dict):
        if event.get("status") == "cancelled":
            task.due_date = None
        else:
            task.content = (event.get("summary") or task.content)[:500]
            start = event.get("start", {})
            if "dateTime" in start:
                task.due_at = datetime.fromisoformat(start["dateTime"])
                task.due_date = task.due_at.astimezone(zone(member_zone(task.owner))).date()
            elif "date" in start:
                task.due_date, task.due_at = date.fromisoformat(start["date"]), None
        if task.changed("content") or task.changed("due_date") or task.changed("due_at"):
            if not task.due_rule:
                task.due_string = ""
            task.save()


class Push(models.Model):
    """A task whose event needs bringing up to date; gone once it is."""

    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name="pushes")
    task_id = models.UUIDField()
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=tz.now, db_index=True)
    last_error = models.TextField(blank=True)

    class Meta:
        verbose_name = _("pending push")
        verbose_name_plural = _("pending pushes")
        constraints = [
            models.UniqueConstraint(fields=("connection", "task_id"), name="todos_google_one_push")
        ]

    def __str__(self) -> str:
        return str(self.task_id)


@background
def push_pending(connection_id: str):
    if connection := Connection.objects.filter(pk=connection_id).first():
        connection.push_pending()


@background
def pull_changes(connection_id: str):
    if connection := Connection.objects.filter(pk=connection_id).first():
        try:
            connection.pull()
        except RefreshError as error:
            connection.revoked(error)


def connections_for(project_id):
    project = Project.objects.filter(pk=project_id).first()
    if project is None:
        return Connection.objects.none()
    return Connection.objects.filter(
        user_id__in=project.people_ids(), status=ConnectionStatus.CONNECTED
    )


@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def task_saved(sender, instance, **kwargs):
    for connection in connections_for(instance.project_id):
        connection.queue([instance.pk])


@receiver(tasks_changed)
def tasks_done(sender, ids, **kwargs):
    projects = set(Task.objects.filter(pk__in=ids).values_list("project_id", flat=True))
    for project in projects:
        for connection in connections_for(project):
            connection.queue(ids)


@receiver(member_left)
def left_project(sender, project, user, **kwargs):
    if connection := Connection.objects.filter(user=user).first():
        connection.queue(Task.objects.filter(project=project))


@receiver(reminder_due)
def check_connection(sender, reminder, **kwargs):
    """Every quarter hour: retry what failed, and renew the channel before it lapses."""
    connection = reminder.target
    if not isinstance(connection, Connection) or connection.status != "connected":
        return
    connection.push_pending()
    soon = tz.now() + timedelta(days=1)
    if not connection.channel_expires_at or connection.channel_expires_at < soon:
        try:
            connection.watch()
        except RefreshError as error:
            connection.revoked(error)
        except (HttpError, OSError) as error:
            connection.last_error = str(error)[:2000]
            connection.save(update_fields=("last_error", "updated_at"))
