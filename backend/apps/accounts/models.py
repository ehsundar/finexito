"""Identity only.

A User is the person who can authenticate. Anything app-specific about them
(display name, avatar, preferences) belongs on their Profile, never here.

Everyone signs in with Google, so nobody has a password. Accounts are created on
first sign-in; staff and superusers are ordinary accounts promoted afterwards
with `manage.py make_superuser`.
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import UUIDModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, *args, **kwargs):
        # Keeps `createsuperuser` from making a password account.
        raise NotImplementedError(
            "Sign in with Google first, then run: manage.py make_superuser <email>"
        )


class User(UUIDModel, AbstractBaseUser, PermissionsMixin):
    # The system user: owns whatever the site does on its own behalf. Created by
    # a migration, never signs in.
    SYSTEM_ID = uuid.UUID(int=1)

    email = models.EmailField(_("email address"), unique=True, db_index=True)
    # Google's stable account id (the `sub` claim); the email can change.
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ("-date_joined",)

    def __str__(self) -> str:
        return self.email
