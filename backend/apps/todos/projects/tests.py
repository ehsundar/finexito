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


class SharingTests(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.shared = self.project("Home")
        self.other = User.objects.create_user(email="other@example.com")

    def join(self, user=None, project=None):
        self.authenticate(user or self.other)
        response = self.client.post(
            reverse("todo-join", args=[(project or self.shared).invite_token])
        )
        self.authenticate(self.user)
        return response

    def test_preview_needs_no_sign_in(self):
        self.client.force_authenticate(None)

        response = self.client.get(reverse("todo-join", args=[self.shared.invite_token]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Home")
        self.assertEqual(response.data["invited_by"]["email"], "someone@example.com")
        self.assertFalse(response.data["is_member"])

    def test_joining_shows_the_project_with_the_joiners_own_place(self):
        self.assertEqual(self.join().status_code, 200)

        self.authenticate(self.other)
        listed = self.client.get(reverse("todo-project-list")).data
        home = next(p for p in listed if p["name"] == "Home")
        self.assertFalse(home["is_owner"])
        self.assertTrue(home["is_shared"])
        mine = self.client.post(reverse("todo-project-list"), {"name": "Mine"}).data
        response = self.client.patch(
            reverse("todo-project-detail", args=[self.shared.pk]),
            {"parent": mine["id"], "colour": "red", "is_favourite": True},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["parent"], mine["id"])
        self.shared.refresh_from_db()
        self.assertEqual((self.shared.parent, self.shared.colour), (None, "neutral"))

    def test_collaborators_cannot_rename_delete_or_share(self):
        self.join()
        self.authenticate(self.other)
        url = reverse("todo-project-detail", args=[self.shared.pk])

        self.assertEqual(self.client.patch(url, {"name": "Mine"}).status_code, 403)
        self.assertEqual(self.client.patch(url, {"is_archived": True}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        link = reverse("todo-project-invite-link", args=[self.shared.pk])
        self.assertEqual(self.client.get(link).status_code, 403)

    def test_resetting_the_link_stops_the_old_one(self):
        old = self.shared.invite_token
        link = reverse("todo-project-invite-link", args=[self.shared.pk])

        new = self.client.post(link).data["token"]

        self.assertNotEqual(new, old)
        self.assertEqual(self.client.get(reverse("todo-join", args=[old])).status_code, 404)
        self.client.delete(link)
        self.shared.refresh_from_db()
        self.assertEqual(self.shared.invite_token, "")

    def test_the_inbox_cannot_be_shared(self):
        link = reverse("todo-project-invite-link", args=[self.inbox.pk])

        self.assertEqual(self.client.get(link).status_code, 404)
        self.assertEqual(self.inbox.invite_token, "")

    @override_settings(TODOS_PROJECTS_MAX_COLLABORATORS=1)
    def test_a_full_project_turns_people_away(self):
        self.join()

        response = self.join(User.objects.create_user(email="third@example.com"))

        self.assertEqual(response.status_code, 400)

    def test_collaborators_list_remove_and_leave(self):
        self.join()
        third = User.objects.create_user(email="third@example.com")
        self.join(third)
        url = reverse("todo-project-collaborators", args=[self.shared.pk])

        people = self.client.get(url).data
        self.assertEqual(
            [p["email"] for p in people],
            ["someone@example.com", "other@example.com", "third@example.com"],
        )
        self.assertEqual(self.client.delete(f"{url}?user={third.pk}").status_code, 204)
        self.authenticate(self.other)
        self.assertEqual(self.client.delete(f"{url}?user={self.user.pk}").status_code, 403)
        self.assertEqual(self.client.delete(f"{url}?user={self.other.pk}").status_code, 204)
        self.assertEqual(self.shared.members.count(), 0)

    def test_the_owner_cannot_leave(self):
        url = reverse("todo-project-collaborators", args=[self.shared.pk])

        self.assertEqual(self.client.delete(f"{url}?user={self.user.pk}").status_code, 400)

    def test_transfer_swaps_places(self):
        child = self.project("Child", parent=self.shared)
        self.join()

        response = self.client.post(
            reverse("todo-project-transfer", args=[self.shared.pk]), {"user": self.other.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_owner"])
        self.shared.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual(self.shared.owner, self.other)
        self.assertTrue(self.shared.members.filter(user=self.user).exists())
        self.assertIsNone(child.parent)

    def test_collaborators_manage_sections_but_cannot_move_them_out(self):
        self.join()
        self.authenticate(self.other)

        made = self.client.post(
            reverse("todo-section-list"), {"project": self.shared.pk, "name": "Kitchen"}
        )
        self.assertEqual(made.status_code, 201)
        mine = self.client.post(reverse("todo-project-list"), {"name": "Mine"}).data
        response = self.client.patch(
            reverse("todo-section-detail", args=[made.data["id"]]), {"project": mine["id"]}
        )
        self.assertEqual(response.status_code, 400)

    def test_reorder_mixes_owned_and_joined_projects(self):
        theirs = Project.objects.create(owner=self.other, name="Theirs")
        self.client.post(reverse("todo-join", args=[theirs.invite_token]))
        a = self.project("A")

        response = self.client.post(
            reverse("todo-project-reorder"),
            [str(theirs.pk), str(a.pk), str(self.shared.pk)],
            format="json",
        )

        self.assertEqual(response.status_code, 204)
        names = [p["name"] for p in self.client.get(reverse("todo-project-list")).data]
        self.assertEqual(names, ["Inbox", "Theirs", "A", "Home"])
