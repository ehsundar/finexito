from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse

from apps.common.testing import PlatformTestCase
from apps.todos.models import Label, Project, Section, Task
from apps.todos.views import parse_quick_add

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


class ProjectTests(TodosTestCase):
    def test_list_includes_the_inbox_once(self):
        self.client.get(reverse("todo-project-list"))
        response = self.client.get(reverse("todo-project-list"))

        self.assertEqual([p["name"] for p in response.data], ["Inbox"])
        self.assertTrue(response.data[0]["is_inbox"])

    def test_inbox_cannot_be_renamed_or_deleted(self):
        url = reverse("todo-project-detail", args=[self.inbox.pk])

        self.assertEqual(self.client.patch(url, {"name": "Other"}).status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, 400)

    def test_nesting_stops_at_three_levels(self):
        a = self.project("A")
        b = self.project("B", parent=a)
        c = self.project("C", parent=b)

        with self.assertRaises(ValidationError):
            self.project("D", parent=c)
        # Moving a two-level tree under a two-level tree is four levels.
        top = self.project("Top")
        response = self.client.patch(
            reverse("todo-project-detail", args=[b.pk]), {"parent": top.pk}
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.patch(
            reverse("todo-project-detail", args=[top.pk]), {"parent": a.pk}
        )
        self.assertEqual(response.status_code, 400)

    def test_archiving_takes_sub_projects_and_unarchiving_restores_them(self):
        parent = self.project("Parent")
        child = self.project("Child", parent=parent)
        url = reverse("todo-project-detail", args=[parent.pk])

        self.client.patch(url, {"is_archived": True})
        child.refresh_from_db()
        self.assertTrue(child.is_archived)
        listed = self.client.get(reverse("todo-project-list"), {"archived": "true"}).data
        self.assertEqual({p["name"] for p in listed}, {"Parent", "Child"})

        self.client.patch(url, {"is_archived": False})
        child.refresh_from_db()
        self.assertFalse(child.is_archived)

    def test_others_projects_are_not_found(self):
        theirs = Project.objects.inbox(User.objects.create_user(email="other@example.com"))

        response = self.client.get(reverse("todo-project-detail", args=[theirs.pk]))

        self.assertEqual(response.status_code, 404)

    def test_cannot_nest_under_someone_elses_project(self):
        theirs = Project.objects.create(
            owner=User.objects.create_user(email="other@example.com"), name="Theirs"
        )

        response = self.client.post(
            reverse("todo-project-list"), {"name": "Mine", "parent": theirs.pk}
        )

        self.assertEqual(response.status_code, 400)

    @override_settings(TODOS_MAX_PROJECTS=2)
    def test_project_limit(self):
        self.project("One")

        response = self.client.post(reverse("todo-project-list"), {"name": "Two"})

        self.assertEqual(response.status_code, 400)

    def test_reorder(self):
        a, b, c = self.project("A"), self.project("B"), self.project("C")

        response = self.client.post(
            reverse("todo-project-reorder"), [str(c.pk), str(a.pk), str(b.pk)], format="json"
        )

        self.assertEqual(response.status_code, 204)
        names = [p.name for p in Project.objects.filter(owner=self.user, is_inbox=False)]
        self.assertEqual(names, ["C", "A", "B"])

    def test_reorder_refuses_non_siblings(self):
        a = self.project("A")
        b = self.project("B", parent=a)

        response = self.client.post(
            reverse("todo-project-reorder"), [str(a.pk), str(b.pk)], format="json"
        )

        self.assertEqual(response.status_code, 400)


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

    @override_settings(TODOS_MAX_SECTIONS_PER_PROJECT=1)
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

        with override_settings(TODOS_MAX_EXTRA_BYTES=10):
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


class QuickAddTests(TodosTestCase):
    def quick(self, text, **extra):
        return self.client.post(reverse("todo-task-quick"), {"text": text, **extra}, format="json")

    def test_plain_text_lands_in_the_inbox(self):
        response = self.quick("Buy milk")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["project"], self.inbox.pk)
        self.assertEqual(response.data["content"], "Buy milk")

    def test_tokens(self):
        work = self.project("Client work")
        section = self.section("Next week", project=work)

        response = self.quick("Send invoice #client work /next week @money p1")

        self.assertEqual(response.data["content"], "Send invoice")
        self.assertEqual(response.data["project"], work.pk)
        self.assertEqual(response.data["section"], section.pk)
        self.assertEqual(response.data["priority"], 1)
        self.assertEqual(Label.objects.get(pk=response.data["labels"][0]).name, "money")

    def test_unmatched_and_escaped_tokens_stay_in_the_text(self):
        response = self.quick(r"Read #nowhere and \p1 \@home")

        self.assertEqual(response.data["content"], "Read #nowhere and p1 @home")
        self.assertEqual(response.data["priority"], 4)
        self.assertEqual(response.data["labels"], [])

    def test_prefill_from_a_task(self):
        work = self.project("Work")
        parent = self.task("Parent", project=work)

        response = self.quick("Child", parent=str(parent.pk))

        self.assertEqual((response.data["project"], response.data["parent"]), (work.pk, parent.pk))

    def test_longest_project_name_wins(self):
        short, long = Project(name="Home"), Project(name="Home repairs")

        parsed = parse_quick_add("Fix #home repairs now", {"Home": short, "Home repairs": long})

        self.assertIs(parsed["project"], long)
        self.assertEqual(parsed["content"], "Fix now")


class ThrottleTests(TodosTestCase):
    @override_settings(TODOS_WRITE_RATE="2/hour")
    def test_writes_are_throttled_and_reads_are_not(self):
        for _ in range(2):
            self.client.post(reverse("todo-label-list"), {"name": f"l{_}"})

        self.assertEqual(
            self.client.post(reverse("todo-label-list"), {"name": "z"}).status_code, 429
        )
        self.assertEqual(self.client.get(reverse("todo-label-list")).status_code, 200)
