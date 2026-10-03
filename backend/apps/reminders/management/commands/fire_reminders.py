from django.core.management.base import BaseCommand

from apps.reminders.models import Reminder


class Command(BaseCommand):
    help = "Fire the reminders whose time has come. Run every minute."

    def handle(self, *args, **options):
        self.stdout.write(f"Fired {Reminder.fire_due()} reminder(s).")
