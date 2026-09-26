from django.core.management.base import BaseCommand

from apps.storage import services


class Command(BaseCommand):
    help = "Delete expired upload tickets, leftover temporary files and files with no row."

    def handle(self, *args, **options):
        counts = services.purge()
        self.stdout.write(", ".join(f"{name}: {count}" for name, count in counts.items()))
