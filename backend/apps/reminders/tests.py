from datetime import UTC, datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.reminders.models import Reminder, ReminderStatus, next_occurrence, reminder_due

User = get_user_model()
NOW = datetime(2026, 3, 27, 12, 0, tzinfo=UTC)


class OccurrenceTests(TestCase):
    def test_keeps_the_wall_clock_time_across_summer_time(self):
        start = datetime(2026, 3, 27, 9, 0, tzinfo=UTC)  # 9:00 in London, still GMT
        after = datetime(2026, 3, 28, 12, 0, tzinfo=UTC)

        found = next_occurrence("FREQ=DAILY", "Europe/London", after, start=start)

        # 29 March is the first day of BST: 9:00 there is 8:00 UTC.
        self.assertEqual(found, datetime(2026, 3, 29, 8, 0, tzinfo=UTC))

    def test_the_31st_skips_shorter_months(self):
        start = datetime(2026, 1, 31, tzinfo=UTC)

        found = next_occurrence("FREQ=MONTHLY;BYMONTHDAY=31", "UTC", start, start=start)

        self.assertEqual(found, datetime(2026, 3, 31, tzinfo=UTC))

    def test_none_once_the_series_ends(self):
        start = datetime(2026, 1, 1, tzinfo=UTC)

        self.assertIsNone(
            next_occurrence("FREQ=DAILY;COUNT=2", "UTC", start + timedelta(days=1), start=start)
        )

    def test_an_unknown_zone_reads_as_utc(self):
        start = datetime(2026, 1, 1, 9, tzinfo=UTC)

        found = next_occurrence("FREQ=DAILY", "Nowhere/Else", start, start=start)

        self.assertEqual(found, datetime(2026, 1, 2, 9, tzinfo=UTC))


@mock.patch("django.utils.timezone.now", lambda: NOW)
class ReminderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="someone@example.com")
        self.fired = []
        reminder_due.connect(self.receive)
        self.addCleanup(reminder_due.disconnect, self.receive)

    def receive(self, sender, reminder, **kwargs):
        self.fired.append(reminder.pk)

    def reminder(self, start_at, **fields):
        return Reminder.objects.create(
            user=self.user, target=self.user, start_at=start_at, **fields
        )

    def test_saving_schedules_it_and_a_past_one_is_done(self):
        ahead = self.reminder(NOW + timedelta(hours=1))
        past = self.reminder(NOW - timedelta(hours=1))

        self.assertEqual(ahead.next_at, NOW + timedelta(hours=1))
        self.assertEqual(ahead.status, ReminderStatus.SCHEDULED)
        self.assertIsNone(past.next_at)
        self.assertEqual(past.status, ReminderStatus.DONE)

    def test_moving_the_start_reschedules_it(self):
        reminder = Reminder.objects.get(pk=self.reminder(NOW - timedelta(hours=1)).pk)

        reminder.start_at = NOW + timedelta(days=1)
        reminder.save()

        self.assertEqual(reminder.next_at, NOW + timedelta(days=1))
        self.assertEqual(reminder.status, ReminderStatus.SCHEDULED)

    def test_fires_what_is_due_and_finishes_one_offs(self):
        due = self.reminder(NOW)
        later = self.reminder(NOW + timedelta(minutes=5))

        call_command("fire_reminders", stdout=mock.Mock())

        self.assertEqual(self.fired, [due.pk])
        due.refresh_from_db()
        self.assertEqual(due.status, ReminderStatus.DONE)
        self.assertIsNone(due.next_at)
        self.assertEqual(due.fired_at, NOW)
        later.refresh_from_db()
        self.assertEqual(later.status, ReminderStatus.SCHEDULED)

    def test_fires_once_after_downtime_and_moves_on_from_now(self):
        reminder = self.reminder(NOW - timedelta(days=3), rule="FREQ=HOURLY")
        Reminder.objects.filter(pk=reminder.pk).update(next_at=NOW - timedelta(days=3))

        Reminder.fire_due()

        self.assertEqual(self.fired, [reminder.pk])
        reminder.refresh_from_db()
        self.assertEqual(reminder.next_at, NOW + timedelta(hours=1))

    def test_a_failing_receiver_marks_it_failed_and_the_others_still_fire(self):
        broken = self.reminder(NOW - timedelta(minutes=1))
        fine = self.reminder(NOW)
        Reminder.objects.filter(pk=broken.pk).update(
            next_at=broken.start_at, status=ReminderStatus.SCHEDULED
        )

        def explode(sender, reminder, **kwargs):
            if reminder.pk == broken.pk:
                raise RuntimeError("no luck")

        reminder_due.connect(explode)
        self.addCleanup(reminder_due.disconnect, explode)
        Reminder.fire_due()

        broken.refresh_from_db()
        self.assertEqual(broken.status, ReminderStatus.FAILED)
        self.assertEqual(broken.last_error, "RuntimeError: no luck")
        self.assertIn(fine.pk, self.fired)

        broken.retry()
        reminder_due.disconnect(explode)
        Reminder.fire_due()
        broken.refresh_from_db()
        self.assertEqual(broken.status, ReminderStatus.DONE)

    @override_settings(REMINDERS_MAX_PER_HOUR=2)
    def test_a_member_over_the_hourly_cap_waits(self):
        reminders = [self.reminder(NOW) for _ in range(3)]

        self.assertEqual(Reminder.fire_due(), 2)

        waiting = Reminder.objects.get(status=ReminderStatus.SCHEDULED)
        self.assertIn(waiting, reminders)
        self.assertEqual(waiting.next_at, NOW)
        with mock.patch("django.utils.timezone.now", lambda: NOW + timedelta(minutes=61)):
            self.assertEqual(Reminder.fire_due(), 1)

    def test_target_is_the_row_it_points_at(self):
        self.assertEqual(Reminder.objects.get(pk=self.reminder(NOW).pk).target, self.user)
