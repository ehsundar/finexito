"""Built-in templates: code, like filters. Adding one is adding a subclass of
``BuiltIn``; ``TODOS_TEMPLATES_BUILT_IN`` picks which a deployment offers.

Write the text without product names; rows are as in ``templates.models``.
"""

from django.conf import settings


def task(content, indent=1, due="", priority=4, labels="", description=""):
    return {
        "type": "task",
        "content": content,
        "indent": indent,
        "due": due,
        "priority": priority,
        "labels": labels,
        "description": description,
    }


def section(name):
    return {"type": "section", "content": name}


class BuiltIn:
    slug: str
    name: str
    description: str
    category: str
    rows: list[dict]
    registry: dict[str, "BuiltIn"] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BuiltIn.registry[cls.slug] = cls()

    @classmethod
    def offered(cls) -> list["BuiltIn"]:
        chosen = settings.TODOS_TEMPLATES_BUILT_IN
        return [t for slug, t in cls.registry.items() if not chosen or slug in chosen]


class Trip(BuiltIn):
    slug, name, category = "trip", "Trip", "Personal"
    description = "Book, pack and get going."
    rows = [
        section("Before"),
        task("Book travel", due="+0", priority=2),
        task("Book a place to stay", due="+0", priority=2),
        task("Check passports and visas", due="+1"),
        section("Packing"),
        task("Clothes", due="+5"),
        task("Toiletries", due="+5"),
        task("Chargers and adapters", due="+5"),
        task("Documents", due="+5", priority=1),
        section("Leaving"),
        task("Water the plants", due="+6"),
        task("Take the bins out", due="+6"),
    ]


class Move(BuiltIn):
    slug, name, category = "move", "Moving home", "Personal"
    description = "From giving notice to the first night in."
    rows = [
        task("Give notice", due="+0", priority=1),
        task("Book movers", due="+2", priority=2),
        task("Redirect post", due="+7"),
        section("Accounts"),
        task("Electricity and gas", due="+10"),
        task("Internet", due="+10"),
        task("Update your address", due="+14"),
        task("Bank", indent=2),
        task("Doctor", indent=2),
        section("Packing"),
        task("Get boxes", due="+3"),
        task("Pack room by room", due="+14"),
    ]


class Launch(BuiltIn):
    slug, name, category = "launch", "Product launch", "Work"
    description = "Plan it, build it, announce it, follow up."
    rows = [
        section("Plan"),
        task("Write the brief", due="+0", priority=1),
        task("Agree the date", due="+2"),
        section("Build"),
        task("Finish the work", due="+14", priority=1),
        task("Test it", due="+18"),
        section("Announce"),
        task("Write the announcement", due="+19"),
        task("Send it", due="+21 09:00", priority=1),
        section("Follow up"),
        task("Gather feedback", due="+28"),
        task("Weekly review", due="every monday"),
    ]


class Onboarding(BuiltIn):
    slug, name, category = "onboarding", "Onboarding", "Work"
    description = "A new person's first weeks."
    rows = [
        section("Before day one"),
        task("Set up accounts", due="+0", priority=2),
        task("Send a welcome note", due="+0"),
        section("First week"),
        task("Introductions", due="+3"),
        task("First small task", due="+4"),
        section("First month"),
        task("Check in", due="+14"),
        task("Review together", due="+30"),
    ]
