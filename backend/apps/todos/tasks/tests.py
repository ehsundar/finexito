from datetime import UTC, date, datetime, time, timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from apps.common.testing import PlatformTestCase
from apps.messaging.models import EmailMessage
from apps.profiles.models import Profile
from apps.reminders.models import Reminder, reminder_due
from apps.todos.projects.models import Project, Section
from apps.todos.tasks.dates import Due
from apps.todos.tasks.models import Label, Task

User = get_user_model()


class TodosTestCase(PlatformTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.authenticate()
        self.inbox = Project.objects.inbox(self.user)

    def project(self, name="Work", **fields):
        project = Project(owner=self.user, name=name, **fields)
        project.full_clean()
        project.save()
        return project

    def section(self, name="Section", project=None):
        section = Section(project=project or self.inbox, name=name)
        section.full_clean()
        section.save()
        return section

    def task(self, content="Task", project=None, **fields):
        task = Task(project=project or self.inbox, content=content, **fields)
        task.full_clean()
        task.save()
        return task


class TaskTests(TodosTestCase):
    def test_tasks_nest_four_levels(self):
        node = self.task("L1")
        for level in range(2, 5):
            node = self.task(f"L{level}", parent=node)

        with self.assertRaises(ValidationError):
            self.task("Too deep", parent=node)

    def test_cannot_nest_under_itself(self):
        parent = self.task("Parent")
        child = self.task("Child", parent=parent)

        parent.parent = child
        with self.assertRaises(ValidationError):
            parent.full_clean()

    def test_section_must_be_in_the_tasks_project(self):
        elsewhere = self.section(project=self.project("Work"))

        with self.assertRaises(ValidationError):
            self.task(section=elsewhere)

    def test_sub_tasks_follow_their_parent_into_a_section(self):
        section = self.section()
        parent = self.task("Parent")
        child = self.task("Child", parent=parent)

        self.client.patch(reverse("todo-task-detail", args=[parent.pk]), {"section": section.pk})

        child.refresh_from_db()
        self.assertEqual(child.section, section)

    def test_moving_a_section_takes_its_tasks(self):
        work = self.project("Work")
        section = self.section()
        task = self.task(section=section)

        response = self.client.patch(
            reverse("todo-section-detail", args=[section.pk]), {"project": work.pk}
        )

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.project, work)

    def test_archived_sections_hide_their_tasks(self):
        section = self.section()
        self.task("Hidden", section=section)
        self.task("Shown")

        self.client.patch(reverse("todo-section-detail", args=[section.pk]), {"is_archived": True})
        listed = self.client.get(reverse("todo-task-list"), {"project": self.inbox.pk}).data

        self.assertEqual([t["content"] for t in listed], ["Shown"])

    @override_settings(TODOS_PROJECTS_MAX_SECTIONS=1)
    def test_section_limit(self):
        self.section()

        response = self.client.post(
            reverse("todo-section-list"), {"project": self.inbox.pk, "name": "Two"}
        )

        self.assertEqual(response.status_code, 400)

    def test_moving_a_task_moves_its_sub_tasks_and_un_nests_it(self):
        work = self.project("Work")
        parent = self.task("Parent")
        child = self.task("Child", parent=parent)
        grandchild = self.task("Grandchild", parent=child)

        response = self.client.patch(
            reverse("todo-task-detail", args=[child.pk]), {"project": work.pk}
        )

        self.assertEqual(response.status_code, 200)
        child.refresh_from_db()
        grandchild.refresh_from_db()
        self.assertIsNone(child.parent)
        self.assertEqual(grandchild.project, work)

    def test_nesting_under_a_task_elsewhere_adopts_its_project(self):
        work = self.project("Work")
        parent = self.task("Parent", project=work)
        task = self.task("Task")

        self.client.patch(reverse("todo-task-detail", args=[task.pk]), {"parent": parent.pk})

        task.refresh_from_db()
        self.assertEqual(task.project, work)

    def test_new_tasks_go_to_the_end(self):
        first, second = self.task("One"), self.task("Two")

        self.assertLess(first.order, second.order)

    def test_extra_is_stored_as_is_and_capped(self):
        response = self.client.post(
            reverse("todo-task-list"),
            {"project": str(self.inbox.pk), "content": "X", "extra": {"a": [1, {"b": True}]}},
            format="json",
        )
        self.assertEqual(response.data["extra"], {"a": [1, {"b": True}]})

        with override_settings(TODOS_TASKS_MAX_EXTRA_BYTES=10):
            response = self.client.post(
                reverse("todo-task-list"),
                {"project": str(self.inbox.pk), "content": "X", "extra": {"a": "x" * 20}},
                format="json",
            )
        self.assertEqual(response.status_code, 400)

    def test_cannot_use_someone_elses_labels(self):
        theirs = Label.objects.create(
            owner=User.objects.create_user(email="other@example.com"), name="x"
        )

        response = self.client.post(
            reverse("todo-task-list"),
            {"project": str(self.inbox.pk), "content": "X", "labels": [str(theirs.pk)]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)


class CompletionTests(TodosTestCase):
    def test_closing_a_parent_closes_its_sub_tasks_and_reopening_restores_them(self):
        parent = self.task("Parent")
        child = self.task("Child", parent=parent)

        self.client.post(reverse("todo-task-close", args=[parent.pk]))
        child.refresh_from_db()
        self.assertIsNotNone(child.completed_at)

        self.client.post(reverse("todo-task-reopen", args=[parent.pk]))
        child.refresh_from_db()
        self.assertIsNone(child.completed_at)

    def test_closing_a_sub_task_leaves_the_parent_and_reopening_reopens_it(self):
        parent = self.task("Parent")
        child = self.task("Child", parent=parent)
        child.close()
        parent.refresh_from_db()
        self.assertIsNone(parent.completed_at)

        parent.close()
        child.refresh_from_db()
        child.reopen()
        parent.refresh_from_db()
        self.assertIsNone(parent.completed_at)

    def test_lists_show_open_tasks_unless_asked_for_completed(self):
        done = self.task("Done")
        done.close()
        self.task("Open")

        open_ = self.client.get(reverse("todo-task-list"), {"project": self.inbox.pk}).data
        completed = self.client.get(reverse("todo-task-list"), {"completed": "true"}).data

        self.assertEqual([i["content"] for i in open_], ["Open"])
        self.assertEqual([i["content"] for i in completed], ["Done"])

    def test_sub_task_counts(self):
        parent = self.task("Parent")
        self.task("A", parent=parent).close()
        self.task("B", parent=parent)

        data = self.client.get(reverse("todo-task-detail", args=[parent.pk])).data
        listed = self.client.get(reverse("todo-task-list"), {"parent": "none"}).data

        self.assertIn("subtask_count", data)
        self.assertEqual((listed[0]["subtask_count"], listed[0]["completed_subtask_count"]), (2, 1))


class FilterAndSearchTests(TodosTestCase):
    def test_priority_filter(self):
        self.task("Urgent", priority=1)
        self.task("Calm")

        response = self.client.get(reverse("todo-task-list"), {"filter": "priority-1"})

        self.assertEqual([i["content"] for i in response.data], ["Urgent"])

    def test_unknown_filter_is_not_found(self):
        response = self.client.get(reverse("todo-task-list"), {"filter": "nope"})

        self.assertEqual(response.status_code, 404)

    def test_favouriting_a_filter(self):
        url = reverse("todo-filter-favourite", args=["no-labels"])

        self.assertEqual(self.client.post(url).status_code, 204)
        self.client.post(url)
        filters = {f["slug"]: f for f in self.client.get(reverse("todo-filter-list")).data}
        self.assertTrue(filters["no-labels"]["is_favourite"])
        self.assertFalse(filters["priority-1"]["is_favourite"])

        self.client.delete(url)
        filters = {f["slug"]: f for f in self.client.get(reverse("todo-filter-list")).data}
        self.assertFalse(filters["no-labels"]["is_favourite"])

    def test_search_matches_description_and_skips_archived_projects(self):
        self.task("Plain", description="has the NEEDLE")
        hidden = self.project("Hidden", is_archived=True)
        self.task("needle too", project=hidden)

        response = self.client.get(reverse("todo-task-list"), {"q": "needle"})

        self.assertEqual([i["content"] for i in response.data], ["Plain"])


class LabelTests(TodosTestCase):
    def test_names_are_unique_case_insensitively(self):
        self.client.post(reverse("todo-label-list"), {"name": "home"})

        response = self.client.post(reverse("todo-label-list"), {"name": "HOME"})

        self.assertEqual(response.status_code, 400)

    def test_names_have_no_spaces(self):
        response = self.client.post(reverse("todo-label-list"), {"name": "two words"})

        self.assertEqual(response.status_code, 400)

    def test_deleting_a_label_keeps_its_tasks(self):
        label = Label.objects.create(owner=self.user, name="x")
        task = self.task()
        task.labels.add(label)

        self.client.delete(reverse("todo-label-detail", args=[label.pk]))

        self.assertTrue(Task.objects.filter(pk=task.pk).exists())


class ThrottleTests(TodosTestCase):
    @override_settings(TODOS_PROJECTS_WRITE_RATE="2/hour")
    def test_writes_are_throttled_and_reads_are_not(self):
        for _ in range(2):
            self.client.post(reverse("todo-label-list"), {"name": f"l{_}"})

        self.assertEqual(
            self.client.post(reverse("todo-label-list"), {"name": "z"}).status_code, 429
        )
        self.assertEqual(self.client.get(reverse("todo-label-list")).status_code, 200)


# Wednesday 7 October 2026, 11:00 in London (BST, UTC+1).
NOW = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)
TODAY = date(2026, 10, 7)


class DueParseTests(SimpleTestCase):
    def parse(self, phrase):
        return Due.parse(phrase, TODAY)

    def test_one_off_phrases(self):
        cases = {
            "today": TODAY,
            "tod": TODAY,
            "tomorrow": date(2026, 10, 8),
            "tom": date(2026, 10, 8),
            "monday": date(2026, 10, 12),
            "wed": date(2026, 10, 14),
            "next friday": date(2026, 10, 9),
            "this weekend": date(2026, 10, 10),
            "next week": date(2026, 10, 12),
            "in 3 days": date(2026, 10, 10),
            "in 2 weeks": date(2026, 10, 21),
            "oct 12": date(2026, 10, 12),
            "12/10": date(2026, 10, 12),
            "12 october 2027": date(2027, 10, 12),
            "1st jan": date(2027, 1, 1),
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase):
                due = self.parse(phrase)
                self.assertEqual((due.date, due.time, due.rule), (expected, None, ""))
                self.assertEqual(due.string, phrase)

    def test_times(self):
        self.assertEqual(self.parse("at 5pm").time, time(17))
        self.assertEqual(self.parse("at 5pm").date, TODAY)
        self.assertEqual(self.parse("17:00").time, time(17))
        tomorrow = self.parse("tomorrow 9:30am")
        self.assertEqual((tomorrow.date, tomorrow.time), (date(2026, 10, 8), time(9, 30)))
        self.assertEqual(self.parse("12am").time, time(0))

    def test_no_date_clears(self):
        self.assertEqual(self.parse("no date"), Due())

    def test_recurring_phrases(self):
        cases = {
            "every day": ("FREQ=DAILY", TODAY),
            "daily": ("FREQ=DAILY", TODAY),
            "every weekday": ("FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", TODAY),
            "every monday": ("FREQ=WEEKLY;BYDAY=MO", date(2026, 10, 12)),
            "every mon, fri": ("FREQ=WEEKLY;BYDAY=MO,FR", date(2026, 10, 9)),
            "every 2 weeks": ("FREQ=WEEKLY;INTERVAL=2", TODAY),
            "every other week": ("FREQ=WEEKLY;INTERVAL=2", TODAY),
            "every other friday": ("FREQ=WEEKLY;INTERVAL=2;BYDAY=FR", date(2026, 10, 9)),
            "every month on the 1st": ("FREQ=MONTHLY;BYMONTHDAY=1", date(2026, 11, 1)),
            "every last day": ("FREQ=MONTHLY;BYMONTHDAY=-1", date(2026, 10, 31)),
            "every year": ("FREQ=YEARLY", TODAY),
            "every 12 oct": ("FREQ=YEARLY;BYMONTH=10;BYMONTHDAY=12", date(2026, 10, 12)),
            "every 3 days starting oct 9": ("FREQ=DAILY;INTERVAL=3", date(2026, 10, 9)),
            "every day until dec 1": ("FREQ=DAILY;UNTIL=20261201T235959", TODAY),
            "every day for 5 times": ("FREQ=DAILY;COUNT=5", TODAY),
        }
        for phrase, (rule, first) in cases.items():
            with self.subTest(phrase):
                due = self.parse(phrase)
                self.assertEqual(due.rule.split("\nRRULE:")[1], rule)
                self.assertEqual(due.date, first)
                self.assertFalse(due.from_completion)

    def test_recurring_with_a_time_and_from_completion(self):
        due = self.parse("every! day at 9am")

        self.assertEqual(due.time, time(9))
        self.assertTrue(due.from_completion)
        self.assertEqual(due.rule, "DTSTART:20261007T090000\nRRULE:FREQ=DAILY")

    def test_nonsense_is_refused(self):
        for phrase in ("", "gibberish", "every banana", "in many days", "25:00", "every 0 days"):
            with self.subTest(phrase), self.assertRaises(ValueError):
                self.parse(phrase)

    def test_finds_a_phrase_in_a_task(self):
        due, span, rest = Due.find("Pay rent every month on the 1st #Home p1", TODAY)

        self.assertEqual(due.rule.split("\nRRULE:")[1], "FREQ=MONTHLY;BYMONTHDAY=1")
        self.assertEqual(span, (9, 31))
        self.assertEqual(rest, "Pay rent #Home p1")

    def test_a_backslash_keeps_a_phrase_as_text(self):
        due, _span, rest = Due.find(r"Call \Tom tomorrow", TODAY)

        self.assertEqual(due.date, date(2026, 10, 8))
        self.assertEqual(rest, "Call Tom")

    def test_nothing_to_find(self):
        self.assertIsNone(Due.find("Buy milk", TODAY))


class DatedTestCase(TodosTestCase):
    def setUp(self):
        super().setUp()
        clock = mock.patch("django.utils.timezone.now", lambda: NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.profile = Profile.objects.create(user=self.user, timezone="Europe/London")

    def due(self, task, phrase):
        response = self.client.patch(
            reverse("todo-task-detail", args=[task.pk]), {"due_string": phrase}
        )
        self.assertEqual(response.status_code, 200, response.data)
        task.refresh_from_db()
        return response.data

    def close(self, task):
        response = self.client.post(reverse("todo-task-close", args=[task.pk]))
        task.refresh_from_db()
        return response.data


class DueDateTests(DatedTestCase):
    def test_a_typed_date_and_time_is_stored_as_an_instant(self):
        data = self.due(self.task(), "tomorrow 9am")

        self.assertEqual((data["due_date"], data["due_time"]), ("2026-10-08", "09:00"))
        self.assertEqual(data["due_string"], "tomorrow 9am")
        self.assertEqual(Task.objects.get().due_at, datetime(2026, 10, 8, 8, tzinfo=UTC))

    def test_a_timed_task_stays_put_when_the_member_travels(self):
        task = self.task()
        self.due(task, "tomorrow 9am")
        self.profile.timezone = "America/New_York"
        self.profile.save()

        data = self.client.get(reverse("todo-task-detail", args=[task.pk])).data

        self.assertEqual((data["due_date"], data["due_time"]), ("2026-10-08", "04:00"))

    def test_a_phrase_that_does_not_parse_changes_nothing(self):
        task = self.task()
        self.due(task, "friday")

        response = self.client.patch(
            reverse("todo-task-detail", args=[task.pk]), {"due_string": "someday soon"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Couldn't understand that date.", str(response.data))
        task.refresh_from_db()
        self.assertEqual(task.due_date, date(2026, 10, 9))

    def test_setting_the_date_keeps_the_time(self):
        task = self.task()
        self.due(task, "tomorrow 9am")

        data = self.client.patch(
            reverse("todo-task-detail", args=[task.pk]), {"due_date": "2026-10-20"}
        ).data

        self.assertEqual((data["due_date"], data["due_time"]), ("2026-10-20", "09:00"))
        self.assertEqual(data["due_string"], "")

    def test_no_date_clears_everything(self):
        task = self.task()
        self.due(task, "every day at 9am")

        data = self.due(task, "no date")

        self.assertEqual(
            (data["due_date"], data["due_time"], data["is_recurring"]), (None, None, False)
        )
        self.assertEqual(task.due_rule, "")

    def test_overdue(self):
        self.task("Yesterday", due_date=date(2026, 10, 6))
        self.task("Earlier", due_date=TODAY, due_at=NOW - timedelta(hours=1))
        self.task("Later", due_date=TODAY, due_at=NOW + timedelta(hours=1))
        self.task("Today", due_date=TODAY)

        overdue = {
            t["content"]: t["is_overdue"] for t in self.client.get(reverse("todo-task-list")).data
        }

        self.assertEqual(
            overdue, {"Yesterday": True, "Earlier": True, "Later": False, "Today": False}
        )

    def test_parse_endpoint(self):
        url = reverse("todo-date-parse")

        found = self.client.post(url, {"text": "Gym every mon, fri at 7am", "find": True}).data
        self.assertEqual(found["content"], "Gym")
        self.assertEqual(found["match"], [4, 25])
        self.assertEqual(found["due"]["date"], "2026-10-09")
        self.assertEqual(found["due"]["time"], "07:00")
        self.assertTrue(found["due"]["is_recurring"])

        self.assertIsNone(self.client.post(url, {"text": "Gym", "find": True}).data["due"])
        self.assertEqual(self.client.post(url, {"text": "nonsense"}).status_code, 400)


class RecurrenceTests(DatedTestCase):
    def test_completing_moves_it_to_the_next_date_and_records_the_completion(self):
        task = self.task("Water plants")
        self.due(task, "every monday")
        sub = self.task("Fill the can", parent=task)
        sub.close()

        data = self.close(task)

        self.assertIsNone(data["completed_at"])
        self.assertEqual(data["due_date"], "2026-10-19")
        sub.refresh_from_db()
        self.assertIsNone(sub.completed_at)
        done = task.completions.get()
        self.assertEqual((done.content, done.due_date), ("Water plants", date(2026, 10, 12)))
        self.assertIsNotNone(done.completed_at)

    def test_an_overdue_task_moves_past_today(self):
        task = self.task()
        self.due(task, "every day")
        Task.objects.filter(pk=task.pk).update(due_date=date(2026, 10, 4))

        self.assertEqual(self.close(task)["due_date"], "2026-10-08")

    def test_every_bang_counts_from_completion(self):
        task = self.task()
        self.due(task, "every! 3 days starting oct 9")

        self.assertEqual(self.close(task)["due_date"], "2026-10-10")

    def test_keeps_its_time(self):
        task = self.task()
        self.due(task, "every day at 9am starting oct 8")

        data = self.close(task)

        self.assertEqual((data["due_date"], data["due_time"]), ("2026-10-09", "09:00"))

    def test_closes_once_the_series_runs_out(self):
        task = self.task()
        self.due(task, "every day for 2 times")

        self.close(task)
        self.assertIsNone(task.completed_at)
        self.close(task)
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(task.completions.count(), 1)

    def test_reopening_undoes_the_last_completion(self):
        task = self.task()
        self.due(task, "every monday")
        self.close(task)

        data = self.client.post(reverse("todo-task-reopen", args=[task.pk])).data

        self.assertEqual(data["due_date"], "2026-10-12")
        self.assertFalse(task.completions.exists())

    def test_recently_completed_lists_each_completion(self):
        task = self.task("Stretch")
        self.due(task, "every day")
        self.close(task)
        self.close(task)

        response = self.client.get(reverse("todo-task-list"), {"filter": "recently-completed"})

        self.assertEqual([t["content"] for t in response.data], ["Stretch", "Stretch"])


class TodayAndUpcomingTests(DatedTestCase):
    def test_today_lists_overdue_then_today_timed_first(self):
        work = self.project("Work")
        self.task("Old", due_date=date(2026, 10, 1))
        self.task("Plain", due_date=TODAY, priority=4)
        self.task("Urgent", due_date=TODAY, priority=1, project=work)
        self.task("Noon", due_date=TODAY, due_at=datetime(2026, 10, 7, 11, tzinfo=UTC))
        self.task("Tomorrow", due_date=date(2026, 10, 8))
        self.task("Undated")
        self.task("Done", due_date=TODAY).close()

        response = self.client.get(reverse("todo-task-list"), {"view": "today"})

        self.assertEqual([t["content"] for t in response.data], ["Old", "Noon", "Urgent", "Plain"])

    def test_upcoming_is_a_range_of_days(self):
        self.task("Before", due_date=TODAY)
        self.task("Friday", due_date=date(2026, 10, 9))
        self.task(
            "Saturday 9am",
            due_date=date(2026, 10, 10),
            due_at=datetime(2026, 10, 10, 8, tzinfo=UTC),
        )
        self.task("After", due_date=date(2026, 10, 11))

        response = self.client.get(
            reverse("todo-task-list"),
            {"view": "upcoming", "from": "2026-10-08", "to": "2026-10-10"},
        )

        self.assertEqual([t["content"] for t in response.data], ["Friday", "Saturday 9am"])
        self.assertEqual(
            self.client.get(
                reverse("todo-task-list"), {"view": "upcoming", "from": "nope"}
            ).status_code,
            400,
        )

    def test_reschedule_moves_tasks_and_keeps_their_times(self):
        plain = self.task("Plain", due_date=date(2026, 10, 1))
        timed = self.task()
        self.due(timed, "oct 2 at 9am")

        response = self.client.post(
            reverse("todo-task-reschedule"),
            {"tasks": [str(plain.pk), str(timed.pk)], "date": "2026-10-07"},
            format="json",
        )

        self.assertEqual(response.status_code, 204)
        plain.refresh_from_db()
        timed.refresh_from_db()
        self.assertEqual(plain.due_date, TODAY)
        self.assertEqual(timed.due_at, datetime(2026, 10, 7, 8, tzinfo=UTC))
        self.assertEqual(timed.due_string, "")

    def test_reschedule_refuses_others_tasks(self):
        theirs = Task.objects.create(
            project=Project.objects.inbox(User.objects.create_user(email="o@example.com")),
            content="Theirs",
        )

        response = self.client.post(
            reverse("todo-task-reschedule"),
            {"tasks": [str(theirs.pk)], "date": "2026-10-07"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_date_filters(self):
        self.task("Overdue", due_date=date(2026, 10, 1))
        self.task("Soon", due_date=date(2026, 10, 13))
        self.task("Later", due_date=date(2026, 10, 14))
        self.task("Undated")
        self.due(self.task("Daily"), "every day")

        def listed(slug):
            response = self.client.get(reverse("todo-task-list"), {"filter": slug})
            return {t["content"] for t in response.data}

        self.assertEqual(listed("overdue"), {"Overdue"})
        self.assertEqual(listed("next-7-days"), {"Soon", "Daily"})
        self.assertEqual(listed("no-due-date"), {"Undated"})
        self.assertEqual(listed("recurring"), {"Daily"})


class TaskReminderTests(DatedTestCase):
    def reminders(self, task):
        return self.client.get(reverse("todo-task-reminders", args=[task.pk])).data

    def test_a_timed_task_gets_the_default_reminder(self):
        task = self.task()
        self.due(task, "tomorrow 9am")

        [reminder] = self.reminders(task)

        self.assertEqual(reminder["minutes_before"], 30)
        self.assertEqual(reminder["next_at"], "2026-10-08T07:30:00Z")
        # Moving the time doesn't add another.
        self.due(task, "tomorrow 10am")
        self.assertEqual(len(self.reminders(task)), 1)

    def test_the_default_can_be_changed_or_turned_off(self):
        self.profile.extra = {"todos_reminder_before": "off"}
        self.profile.save()
        task = self.task()
        self.due(task, "tomorrow 9am")
        self.assertEqual(self.reminders(task), [])

        self.profile.extra = {"todos_reminder_before": "10"}
        self.profile.save()
        other = self.task()
        self.due(other, "tomorrow 9am")
        self.assertEqual(self.reminders(other)[0]["minutes_before"], 10)

    def test_relative_reminders_follow_the_due_time_and_go_with_the_date(self):
        task = self.task()
        self.due(task, "every day at 9am starting oct 8")
        absolute = self.client.post(
            reverse("todo-task-reminders", args=[task.pk]), {"at": "2026-10-20T12:00:00Z"}
        )
        self.assertEqual(absolute.status_code, 201)

        self.close(task)
        times = sorted(r["next_at"] for r in self.reminders(task))
        self.assertEqual(times, ["2026-10-09T07:30:00Z", "2026-10-20T12:00:00Z"])

        self.due(task, "no date")
        self.assertEqual(self.reminders(task), [])

    def test_a_relative_reminder_needs_a_time(self):
        task = self.task(due_date=TODAY)

        response = self.client.post(
            reverse("todo-task-reminders", args=[task.pk]), {"minutes_before": 10}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.post(reverse("todo-task-reminders", args=[task.pk]), {}).status_code, 400
        )

    @override_settings(TODOS_TASKS_MAX_REMINDERS=1)
    def test_reminder_limit(self):
        task = self.task()
        self.due(task, "tomorrow 9am")

        response = self.client.post(
            reverse("todo-task-reminders", args=[task.pk]), {"at": "2026-10-20T12:00:00Z"}
        )

        self.assertEqual(response.status_code, 400)

    def test_deleting_a_reminder_and_others_are_not_found(self):
        task = self.task()
        self.due(task, "tomorrow 9am")
        [reminder] = self.reminders(task)
        theirs = Reminder.objects.create(
            user=self.user, target=self.user, start_at=NOW + timedelta(days=1)
        )

        self.assertEqual(
            self.client.delete(reverse("todo-reminder-detail", args=[theirs.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.delete(reverse("todo-reminder-detail", args=[reminder["id"]])).status_code,
            204,
        )
        self.assertEqual(self.reminders(task), [])

    def test_deleting_the_task_deletes_its_reminders(self):
        task = self.task()
        self.due(task, "tomorrow 9am")

        self.client.delete(reverse("todo-task-detail", args=[task.pk]))

        self.assertFalse(Reminder.objects.exists())

    def fire(self, task):
        Reminder.objects.filter(object_id=task.pk).update(next_at=NOW)
        with self.captureOnCommitCallbacks(execute=True):
            Reminder.fire_due()

    def test_firing_emails_the_member(self):
        task = self.task("Call the bank")
        self.due(task, "tomorrow 9am")

        self.fire(task)

        email = EmailMessage.objects.get()
        self.assertEqual(email.to, "someone@example.com")
        self.assertEqual(email.subject, "Reminder: Call the bank")
        self.assertIn("Due 8 Oct, 09:00", email.body)
        self.assertIn("In Inbox", email.body)
        self.assertIn(f"/todos/task?id={task.pk}", email.body)
        self.assertIn(settings.SITE_NAME, email.body)

    def test_no_email_for_a_completed_task_or_a_member_who_opted_out(self):
        task = self.task()
        self.due(task, "tomorrow 9am")
        task.close()
        self.fire(task)

        task.reopen()
        self.profile.extra = {"todos_reminder_emails": "false"}
        self.profile.save()
        self.fire(task)

        self.assertFalse(EmailMessage.objects.exists())


class SharedTaskTests(DatedTestCase):
    def setUp(self):
        super().setUp()
        self.home = Project.objects.create(owner=self.user, name="Home")
        self.other = User.objects.create_user(email="other@example.com")
        Profile.objects.create(user=self.other, timezone="Europe/London", display_name="Other")
        self.home.join(self.other)

    def test_collaborators_see_and_edit_tasks(self):
        task = self.task("Shop", project=self.home)
        self.authenticate(self.other)

        listed = self.client.get(reverse("todo-task-list"), {"project": self.home.pk}).data
        self.assertEqual([t["content"] for t in listed], ["Shop"])
        response = self.client.patch(
            reverse("todo-task-detail", args=[task.pk]), {"content": "Shop now"}
        )
        self.assertEqual(response.status_code, 200)
        made = self.client.post(
            reverse("todo-task-list"), {"project": self.home.pk, "content": "Cook"}
        )
        self.assertEqual(str(made.data["created_by"]), str(self.other.pk))

    def test_collaborators_cannot_move_tasks_out(self):
        task = self.task("Shop", project=self.home)
        self.authenticate(self.other)
        mine = Project.objects.inbox(self.other)

        response = self.client.patch(
            reverse("todo-task-detail", args=[task.pk]), {"project": mine.pk}
        )

        self.assertEqual(response.status_code, 400)

    def test_assigning_someone_else_emails_them(self):
        task = self.task("Shop", project=self.home)

        response = self.client.patch(
            reverse("todo-task-detail", args=[task.pk]), {"assignee": self.other.pk}
        )

        self.assertEqual(response.status_code, 200)
        email = EmailMessage.objects.get(extra__purpose="todos_assigned")
        self.assertEqual(email.to, "other@example.com")
        # Assigning yourself sends nothing.
        self.client.patch(reverse("todo-task-detail", args=[task.pk]), {"assignee": self.user.pk})
        self.assertEqual(EmailMessage.objects.filter(extra__purpose="todos_assigned").count(), 1)

    def test_only_people_in_the_project_can_be_assigned(self):
        task = self.task("Shop", project=self.home)
        stranger = User.objects.create_user(email="stranger@example.com")

        response = self.client.patch(
            reverse("todo-task-detail", args=[task.pk]), {"assignee": stranger.pk}
        )

        self.assertEqual(response.status_code, 400)

    def test_moving_to_a_project_without_the_assignee_unassigns(self):
        task = self.task("Shop", project=self.home, assignee=self.other)

        self.client.patch(reverse("todo-task-detail", args=[task.pk]), {"project": self.inbox.pk})

        task.refresh_from_db()
        self.assertIsNone(task.assignee)

    def test_assigned_filters(self):
        self.task("Mine", project=self.home, assignee=self.user)
        self.task("Theirs", project=self.home, assignee=self.other)

        def names(slug):
            response = self.client.get(reverse("todo-task-list"), {"filter": slug})
            return [t["content"] for t in response.data]

        self.assertEqual(names("assigned-to-me"), ["Mine"])
        self.assertEqual(names("assigned-to-others"), ["Theirs"])

    def test_each_person_sees_and_sets_only_their_labels(self):
        task = self.task("Shop", project=self.home)
        mine = Label.objects.create(owner=self.user, name="errand")
        theirs = Label.objects.create(owner=self.other, name="weekend")
        task.labels.add(mine)
        self.authenticate(self.other)

        url = reverse("todo-task-detail", args=[task.pk])
        self.assertEqual(self.client.get(url).data["labels"], [])
        response = self.client.patch(url, {"labels": [theirs.pk]}, format="json")
        self.assertEqual(response.data["labels"], [str(theirs.pk)])
        self.assertEqual(set(task.labels.all()), {mine, theirs})
        # Someone else's label isn't theirs to set.
        response = self.client.patch(url, {"labels": [mine.pk]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_the_default_reminder_goes_to_the_assignee_or_everyone(self):
        unassigned = self.task("Shop", project=self.home)
        assigned = self.task("Cook", project=self.home, assignee=self.other)

        self.due(unassigned, "tomorrow 9am")
        self.due(assigned, "tomorrow 9am")

        self.assertEqual({r.user for r in unassigned.reminders.all()}, {self.user, self.other})
        self.assertEqual([r.user for r in assigned.reminders.all()], [self.other])
        # Each sees only their own.
        listed = self.client.get(reverse("todo-task-reminders", args=[assigned.pk])).data
        self.assertEqual(listed, [])

    def test_leaving_takes_assignments_reminders_and_labels(self):
        task = self.task("Shop", project=self.home, assignee=self.other)
        self.due(task, "tomorrow 9am")
        label = Label.objects.create(owner=self.other, name="weekend")
        task.labels.add(label)

        self.home.remove(self.other)

        task.refresh_from_db()
        self.assertIsNone(task.assignee)
        self.assertFalse(task.reminders.filter(user=self.other).exists())
        self.assertFalse(task.labels.exists())
        self.authenticate(self.other)
        self.assertEqual(
            self.client.get(reverse("todo-task-detail", args=[task.pk])).status_code, 404
        )

    def test_reminder_emails_go_to_the_reminders_member(self):
        task = self.task("Shop", project=self.home, assignee=self.other)
        self.due(task, "tomorrow 9am")
        reminder = task.reminders.get()

        reminder_due.send(Reminder, reminder=reminder)

        self.assertEqual(
            EmailMessage.objects.get(extra__purpose="todos_reminder").to, "other@example.com"
        )
