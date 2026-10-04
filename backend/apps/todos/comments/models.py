"""Comments on a task or a project, each with at most one attached file.

Everyone who can see the task or project sees its comments. Saving a new one
emails the people involved (``Comment.notify()``), grouping a burst of comments
on the same thing into one email.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel
from apps.messaging.models import EmailMessage, MessageStatus
from apps.storage.models import StoredObject
from apps.todos.projects.models import Project
from apps.todos.tasks.models import Task, preference

# A member's preferences, kept in their profile's ``extra``.
COMMENT_EMAILS_KEY = "todos_comment_emails"  # "false" turns them off
PROJECT_COMMENT_EMAILS_KEY = "todos_project_comment_emails"  # "true" turns them on

ATTACHMENT_PURPOSE = "todos_comment"


class CommentQuerySet(models.QuerySet):
    def visible_to(self, user):
        return self.filter(
            models.Q(task__in=Task.objects.visible_to(user))
            | models.Q(project__in=Project.objects.visible_to(user))
        )


class Comment(BaseModel):
    task = models.ForeignKey(
        Task, null=True, blank=True, on_delete=models.CASCADE, related_name="comments"
    )
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todo_comments"
    )
    text = models.TextField(max_length=15_000, blank=True, help_text=_("Markdown."))
    attachment = models.OneToOneField(
        StoredObject,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="todo_comment",
    )
    edited_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = CommentQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        verbose_name = _("comment")
        verbose_name_plural = _("comments")
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(task__isnull=True) ^ models.Q(project__isnull=True),
                name="todos_comment_on_one_thing",
                violation_error_message=_("Comment on a task or a project."),
            )
        ]

    def __str__(self) -> str:
        return self.text[:60] or "(file)"

    @property
    def where(self) -> Project:
        """The project it's in, directly or through its task."""
        return self.task.project if self.task_id else self.project

    def clean(self):
        super().clean()
        self.text = self.text.strip()
        if not self.text and not self.attachment_id:
            raise ValidationError({"text": _("Write something, or attach a file.")})
        if self.attachment_id and self._state.adding:
            attachment = self.attachment
            if (
                attachment.owner_id != self.author_id
                or not attachment.is_ready
                or attachment.extra.get("purpose") != ATTACHMENT_PURPOSE
                or Comment.objects.filter(attachment=attachment).exists()
            ):
                raise ValidationError({"attachment": _("Upload the file first.")})

    def save(self, *args, **kwargs):
        adding = self._state.adding
        super().save(*args, **kwargs)
        if adding and self.task_id:
            Task.objects.filter(pk=self.task_id).update(
                comment_count=models.F("comment_count") + 1, updated_at=tz.now()
            )

    def recipients(self) -> list:
        """Who hears about it: on a task, whoever created it or is assigned it; on
        a project, everyone in it who opted in. Never the author, never anyone
        outside the project, never anyone who opted out."""
        project = self.where
        people = set(project.people_ids())
        if self.task_id:
            wanted = {self.task.created_by_id, self.task.assignee_id}
            key, default = COMMENT_EMAILS_KEY, "true"
        else:
            wanted = people
            key, default = PROJECT_COMMENT_EMAILS_KEY, "false"
        ids = (wanted & people) - {self.author_id, None}
        users = get_user_model().objects.filter(pk__in=ids).select_related("profile")
        return [user for user in users if preference(user, key, default) == "true"]

    def notify(self):
        """Email the recipients, adding to an email still waiting to go about the
        same thing, if there is one."""
        author = getattr(getattr(self.author, "profile", None), "display_name", "")
        author = author or self.author.email
        about = self.task.content if self.task_id else self.where.name
        link = (
            f"/todos/task?id={self.task_id}"
            if self.task_id
            else f"/todos/comments?project={self.project_id}"
        )
        entry = f"{author}:\n{self.text or '(attached a file)'}\n\n"
        footer = f"Open it: {settings.PUBLIC_ORIGIN}{link}\n\n— {settings.SITE_NAME}"
        target = str(self.task_id or self.project_id)
        for user in self.recipients():
            with transaction.atomic():
                waiting = (
                    EmailMessage.objects.select_for_update()
                    .filter(
                        to=user.email,
                        status=MessageStatus.PENDING,
                        attempts=0,
                        extra__purpose="todos_comments",
                        extra__about=target,
                    )
                    .first()
                )
                if waiting:
                    waiting.body = waiting.body.removesuffix(footer) + entry + footer
                    waiting.save(update_fields=("body", "updated_at"))
                    continue
                delay = timedelta(minutes=settings.TODOS_COMMENTS_EMAIL_DELAY_MINUTES)
                EmailMessage.objects.create(
                    to=user.email,
                    subject=f"New comments on {about}",
                    body=entry + footer,
                    next_attempt_at=tz.now() + delay,
                    extra={"purpose": "todos_comments", "about": target},
                )


@receiver(post_delete, sender=Comment)
def drop_comment(sender, instance, **kwargs):
    """Deleting a comment deletes its file, and takes it off its task's count."""
    if instance.attachment_id:
        StoredObject.objects.filter(pk=instance.attachment_id).delete()
    if instance.task_id:
        Task.objects.filter(pk=instance.task_id, comment_count__gt=0).update(
            comment_count=models.F("comment_count") - 1, updated_at=tz.now()
        )
