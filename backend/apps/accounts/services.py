"""Email verification: new accounts stay inactive until the link is followed."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

User = get_user_model()


def send_verification_email(user) -> None:
    # The token hashes the user's state, including is_active and last_login, so
    # it stops working as soon as the account is activated.
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.PUBLIC_ORIGIN}/verify-email?uid={uid}&token={token}"
    send_mail(
        subject=f"Confirm your email address for {settings.SITE_NAME}",
        message=f"Follow this link to activate your {settings.SITE_NAME} account:\n\n{link}\n",
        from_email=None,
        recipient_list=[user.email],
    )


def verify_email(uid: str, token: str):
    """Activate the account the link belongs to, or return None if it is invalid."""
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValidationError, ValueError, TypeError, OverflowError):
        return None
    if user.is_active or not default_token_generator.check_token(user, token):
        return None

    user.is_active = True
    user.is_email_verified = True
    user.save(update_fields=["is_active", "is_email_verified"])
    return user
