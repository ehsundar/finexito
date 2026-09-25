from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.programs.models import Program, ProgramDomain


class Command(BaseCommand):
    help = "Create (or update) a program -- one app/website served by this instance."

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("--name", default="")
        parser.add_argument("--description", default="")
        parser.add_argument("--apps", default="profiles", help="Comma-separated enabled apps.")
        parser.add_argument("--domain", action="append", default=[], help="Repeatable hostname.")
        parser.add_argument("--no-self-enrolment", action="store_true")

    def handle(self, *args, **options):
        slug = slugify(options["slug"])
        if not slug:
            raise CommandError("A usable slug is required.")

        program, created = Program.objects.update_or_create(
            slug=slug,
            defaults={
                "name": options["name"] or slug.replace("-", " ").title(),
                "description": options["description"],
                "enabled_apps": [a.strip() for a in options["apps"].split(",") if a.strip()],
                "allow_self_enrolment": not options["no_self_enrolment"],
            },
        )
        for index, host in enumerate(options["domain"]):
            ProgramDomain.objects.update_or_create(
                host=host.lower(), defaults={"program": program, "is_primary": index == 0}
            )

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} program '{program.slug}' ({program.name})."))
