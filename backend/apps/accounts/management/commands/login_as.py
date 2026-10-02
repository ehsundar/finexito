from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Development only: sign in as any email without Google, creating the account if needed."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, email, **options):
        if not settings.DEBUG:
            raise CommandError("login_as only runs with FINEXITO_DEBUG=true.")
        user = User.objects.filter(email=email.lower()).first() or User.objects.create_user(email)
        if user.pk == User.SYSTEM_ID:
            raise CommandError("The system user never signs in.")
        refresh = RefreshToken.for_user(user)
        self.stdout.write(
            f"Open this to sign in as {user.email}:\n\n"
            f"{settings.PUBLIC_ORIGIN}/auth/dev-login?access={refresh.access_token}&refresh={refresh}"
        )
