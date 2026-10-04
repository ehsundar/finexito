from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.common.testing import PlatformTestCase
from apps.todos.projects.models import Project, Section
from apps.todos.tasks.models import Label, Task, member_today
from apps.todos.templates.models import Template, from_csv, to_csv

User = get_user_model()


class TemplateTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.authenticate()
        self.today = member_today(self.user)

    def apply(self, template, **body):
        return self.client.post(
            reverse("todo-template-apply", args=[template]), body, format="json"
        )

    def test_list_offers_built_ins_then_mine(self):
        Template.objects.create(owner=self.user, name="Mine", rows=[])

        listed = self.client.get(reverse("todo-template-list")).data

        self.assertIn("trip", [t["id"] for t in listed])
        self.assertEqual(listed[-1]["name"], "Mine")
        self.assertTrue(listed[-1]["is_mine"])

    @override_settings(TODOS_TEMPLATES_BUILT_IN=["trip"])
    def test_a_deployment_picks_its_built_ins(self):
        listed = self.client.get(reverse("todo-template-list")).data

        self.assertEqual([t["id"] for t in listed], ["trip"])
        self.assertEqual(self.apply("launch").status_code, 404)

    def test_applying_a_built_in_makes_a_project_with_dates_from_today(self):
        response = self.apply("launch")

        self.assertEqual(response.status_code, 201, response.data)
        project = Project.objects.get(pk=response.data["id"])
        self.assertEqual(project.name, "Product launch")
        self.assertEqual(
            list(project.sections.values_list("name", flat=True)),
            ["Plan", "Build", "Announce", "Follow up"],
        )
        brief = project.tasks.get(content="Write the brief")
        self.assertEqual((brief.due_date, brief.priority), (self.today, 1))
        send = project.tasks.get(content="Send it")
        self.assertEqual(send.due_date, self.today + timedelta(days=21))
        self.assertIsNotNone(send.due_at)
        self.assertTrue(project.tasks.get(content="Weekly review").due_rule)

    def test_saving_a_project_and_applying_it_into_another(self):
        source = Project.objects.create(owner=self.user, name="Source")
        kitchen = Section.objects.create(project=source, name="Kitchen")
        top = Task.objects.create(
            project=source, content="Top", due_date=self.today + timedelta(days=2)
        )
        top.labels.add(Label.objects.create(owner=self.user, name="home"))
        parent = Task.objects.create(project=source, section=kitchen, content="Clean")
        Task.objects.create(project=source, section=kitchen, parent=parent, content="Oven")
        Task.objects.create(project=source, content="Done", completed_at="2026-01-01T00:00Z")

        saved = self.client.post(reverse("todo-template-list"), {"project": source.pk})
        self.assertEqual(saved.status_code, 201, saved.data)
        self.assertEqual((saved.data["task_count"], saved.data["section_count"]), (3, 1))
        target = Project.objects.create(owner=self.user, name="Target")
        Section.objects.create(project=target, name="Existing")

        response = self.apply(saved.data["id"], project=str(target.pk))

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            list(target.sections.values_list("name", flat=True)), ["Existing", "Kitchen"]
        )
        oven = target.tasks.get(content="Oven")
        self.assertEqual(oven.parent.content, "Clean")
        copied = target.tasks.get(content="Top")
        self.assertEqual(copied.due_date, self.today + timedelta(days=2))
        self.assertEqual([label.name for label in copied.labels.all()], ["home"])
        self.assertFalse(target.tasks.filter(content="Done").exists())

    def test_a_template_over_a_limit_creates_nothing(self):
        with override_settings(TODOS_PROJECTS_MAX_SECTIONS=2):
            response = self.apply("launch")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Project.objects.filter(name="Product launch").exists())

    def test_new_labels_are_made(self):
        template = Template.objects.create(
            owner=self.user,
            name="T",
            rows=[
                {
                    "type": "task",
                    "content": "A",
                    "indent": 1,
                    "priority": 4,
                    "labels": "fresh",
                    "due": "",
                    "description": "",
                }
            ],
        )

        self.apply(str(template.pk))

        self.assertTrue(Label.objects.filter(owner=self.user, name="fresh").exists())

    def test_csv_round_trip_and_import(self):
        rows = from_csv(
            to_csv(
                [
                    {"type": "section", "content": "S"},
                    {
                        "type": "task",
                        "content": "A",
                        "indent": 1,
                        "priority": 2,
                        "labels": "x y",
                        "due": "+1 09:00",
                        "description": "d",
                    },
                    {"type": "task", "content": "B", "indent": 2},
                ]
            )
        )
        self.assertEqual(rows[1]["labels"], "x y")
        self.assertEqual(rows[2]["indent"], 2)

        upload = SimpleUploadedFile("Packing list.csv", to_csv(rows).encode())
        response = self.client.post(reverse("todo-template-list"), {"file": upload})

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["name"], "Packing list")
        export = self.client.get(reverse("todo-template-export", args=[response.data["id"]]))
        self.assertEqual(export["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("+1 09:00", export.content.decode())

    def test_a_bad_csv_says_which_line(self):
        upload = SimpleUploadedFile("bad.csv", b"type,content,indent\ntask,A,3\n")

        response = self.client.post(reverse("todo-template-list"), {"file": upload})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Line 1", str(response.data))

    def test_project_export(self):
        project = Project.objects.create(owner=self.user, name="Home")
        Task.objects.create(project=project, content="Shop")

        response = self.client.get(reverse("todo-project-export", args=[project.pk]))

        self.assertIn("Shop", response.content.decode())
        other = User.objects.create_user(email="other@example.com")
        self.authenticate(other)
        response = self.client.get(reverse("todo-project-export", args=[project.pk]))
        self.assertEqual(response.status_code, 404)

    def test_only_mine_can_be_renamed_or_deleted(self):
        theirs = Template.objects.create(
            owner=User.objects.create_user(email="other@example.com"), name="Theirs", rows=[]
        )
        mine = Template.objects.create(owner=self.user, name="Mine", rows=[])

        url = reverse("todo-template-detail", args=[theirs.pk])
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(
            self.client.delete(reverse("todo-template-detail", args=["trip"])).status_code, 404
        )
        response = self.client.patch(
            reverse("todo-template-detail", args=[mine.pk]), {"name": "Renamed"}
        )
        self.assertEqual(response.data["name"], "Renamed")

    @override_settings(TODOS_TEMPLATES_MAX_TASKS=1)
    def test_task_limit(self):
        project = Project.objects.create(owner=self.user, name="Big")
        Task.objects.create(project=project, content="A")
        Task.objects.create(project=project, content="B")

        response = self.client.post(reverse("todo-template-list"), {"project": project.pk})

        self.assertEqual(response.status_code, 400)
