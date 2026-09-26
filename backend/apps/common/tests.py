from datetime import UTC, datetime

from django.test import SimpleTestCase

from apps.common.fields import (
    ExtraBoolField,
    ExtraCharField,
    ExtraDateTimeField,
    ExtraIntField,
)


class Thing:
    """Stands in for a BaseModel: the descriptors only need ``extra``."""

    nickname = ExtraCharField(default="")
    visits = ExtraIntField(default=0)
    newsletter = ExtraBoolField(default=False)
    last_seen = ExtraDateTimeField()
    renamed = ExtraIntField(key="stored-as")

    def __init__(self, **extra):
        self.extra = extra


class ExtraFieldTests(SimpleTestCase):
    def test_missing_keys_read_as_the_default(self):
        thing = Thing()

        self.assertEqual(
            (thing.nickname, thing.visits, thing.newsletter, thing.last_seen), ("", 0, False, None)
        )

    def test_values_round_trip_through_strings(self):
        thing = Thing()
        moment = datetime(2026, 9, 26, 12, 30, tzinfo=UTC)

        thing.nickname = "Bob"
        thing.visits = 3
        thing.newsletter = True
        thing.last_seen = moment

        self.assertEqual(
            thing.extra,
            {
                "nickname": "Bob",
                "visits": "3",
                "newsletter": "true",
                "last_seen": "2026-09-26T12:30:00+00:00",
            },
        )
        self.assertEqual(
            (thing.nickname, thing.visits, thing.newsletter, thing.last_seen),
            ("Bob", 3, True, moment),
        )

    def test_unparseable_values_read_as_the_default(self):
        thing = Thing(visits="many", newsletter="yes", last_seen="2026-09-26T12:30:00")

        self.assertEqual((thing.visits, thing.newsletter, thing.last_seen), (0, False, None))

    def test_assigning_none_removes_the_key(self):
        thing = Thing(visits="3")

        thing.visits = None

        self.assertEqual(thing.extra, {})

    def test_assigning_the_wrong_type_raises(self):
        thing = Thing()

        for name, value in (("visits", "3"), ("visits", True), ("newsletter", 1)):
            with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                setattr(thing, name, value)

    def test_naive_datetimes_are_refused(self):
        with self.assertRaises(ValueError):
            Thing().last_seen = datetime(2026, 9, 26, 12, 30)

    def test_key_can_differ_from_the_attribute_name(self):
        thing = Thing()

        thing.renamed = 7

        self.assertEqual(thing.extra, {"stored-as": "7"})
