"""Profile operations shared by the API, the admin and future apps."""

from django.db import transaction

from apps.profiles.models import Profile, ProfileSetting, ProfileStatus
from apps.programs.models import Program


@transaction.atomic
def enrol(user, program: Program, *, display_name: str = "", **extra) -> tuple[Profile, bool]:
    """Enrol a user in a program, returning ``(profile, created)``.

    Idempotent: enrolling twice returns the existing profile untouched.
    """
    status = ProfileStatus.ACTIVE if program.allow_self_enrolment else ProfileStatus.PENDING
    return Profile.objects.get_or_create(
        user=user,
        program=program,
        defaults={
            "display_name": display_name or user.email.split("@")[0],
            "status": status,
            **extra,
        },
    )


@transaction.atomic
def update_settings(profile: Profile, values: dict) -> dict:
    """Merge ``values`` into a profile's overrides.

    A ``None`` value clears the override, falling back to the program default.
    """
    for key, value in values.items():
        if value is None:
            ProfileSetting.objects.filter(profile=profile, key=key).delete()
        else:
            ProfileSetting.objects.update_or_create(
                profile=profile, key=key, defaults={"value": value}
            )
    # Drop any prefetched settings so the resolved view reflects the writes.
    profile._prefetched_objects_cache = {}
    return profile.resolved_settings()
