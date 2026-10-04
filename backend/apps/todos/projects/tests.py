from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse

from apps.common.testing import PlatformTestCase
from apps.todos.projects.models import Project

User = get_user_model()


class ProjectTestCase(PlatformTestCase):
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


class ProjectTests(ProjectTestCase):
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

    @override_settings(TODOS_PROJECTS_MAX=2)
    def test_project_limit(self):
        self.project("One")

        response = self.client.post(reverse("todo-project-list"), {"name": "Two"})

        self.assertEqual(response.status_code, 400)

    def test_list_keeps_the_order(self):
        self.project("A"), self.project("B")

        names = [p["name"] for p in self.client.get(reverse("todo-project-list")).data]

        self.assertEqual(names, ["Inbox", "A", "B"])

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
