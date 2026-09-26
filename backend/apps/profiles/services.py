"""Profile operations shared by the API, the admin and future apps."""

from apps.profiles.models import Profile


def create_profile(user, *, display_name: str = "", **extra) -> Profile:
    return Profile.objects.create(
        user=user, display_name=display_name or user.email.split("@")[0], **extra
    )
