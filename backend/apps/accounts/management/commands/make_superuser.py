from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Make an existing account (created by signing in with Google) a superuser."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--revoke", action="store_true", help="Take the rights away instead.")

    def handle(self, email, revoke, **options):
        user = User.objects.filter(email=email.lower()).exclude(pk=User.SYSTEM_ID).first()
        if user is None:
            raise CommandError(f"No account for {email}. Sign in with Google first.")
        user.is_staff = user.is_superuser = not revoke
        user.save(update_fields=["is_staff", "is_superuser"])
        self.stdout.write(f"{user.email} is {'no longer' if revoke else 'now'} a superuser.")
