"""UI/views этапа 3: сценарии заполнения и права (PostgreSQL)."""
from __future__ import annotations

from datetime import date, timedelta

from django.test import Client, TestCase
from django.urls import reverse

from apps.screenings.models import Assignment
from apps.screenings.services import (
    autosave_draft,
    submit_assignment,
)
from apps.screenings.tests.helpers import (
    assign_for,
    make_admin,
    make_employee,
    make_org,
    make_therapist,
)


class UiFlowTests(TestCase):
    """Заполнение → отправка → возврат → правка → проверка."""

    def setUp(self):
        self.org = make_org()
        self.therapist = make_therapist()
        self.employee = make_employee(
            username="emp_ui",
            birth_date=date(1990, 5, 1),
            org=self.org,
        )
        self.assignment = assign_for(self.employee, self.therapist)
        self.emp_client = Client()
        self.thr_client = Client()
        assert self.emp_client.login(username="emp_ui", password="test-pass-not-secret")
        assert self.thr_client.login(
            username="therapist1", password="test-pass-not-secret"
        )

    def test_full_cycle_fill_return_review(self):
        pk = self.assignment.pk
        detail = reverse("employee_assignment_detail", kwargs={"pk": pk})
        autosave = reverse("employee_assignment_autosave", kwargs={"pk": pk})
        submit_url = reverse("employee_assignment_submit", kwargs={"pk": pk})

        r = self.emp_client.get(detail)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ДЕМО")

        r = self.emp_client.post(
            autosave,
            {
                "answer_demo_smoke": "true",
                "answer_demo_pack_years": "10",
                "answer_demo_note": "черновик",
                "expected_revision": "0",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("Сохранено", r.content.decode())
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Assignment.Status.DRAFT)

        r = self.emp_client.post(
            submit_url,
            {
                "answer_demo_smoke": "true",
                "answer_demo_pack_years": "10",
                "answer_demo_note": "готово",
                "expected_revision": str(self.assignment.draft_revision),
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Assignment.Status.SUBMITTED)

        # Только чтение после submit.
        r = self.emp_client.get(detail)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Отправить анкету")
        self.assertContains(r, "готово")

        r = self.emp_client.post(
            autosave,
            {"answer_demo_note": "поздно", "expected_revision": "99"},
        )
        self.assertIn(r.status_code, (403, 409))

        # Возврат терапевтом.
        return_url = reverse("therapist_return", kwargs={"pk": pk})
        r = self.thr_client.post(
            return_url,
            {
                "comment": "Уточните пачко-леты",
                "new_due_date": str(self.assignment.due_date),
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Assignment.Status.RETURNED)

        r = self.emp_client.get(detail)
        self.assertContains(r, "Уточните пачко-леты")
        self.assertContains(r, "Отправить анкету")

        self.assignment.refresh_from_db()
        r = self.emp_client.post(
            submit_url,
            {
                "answer_demo_smoke": "true",
                "answer_demo_pack_years": "12",
                "answer_demo_note": "исправлено",
                "expected_revision": str(self.assignment.draft_revision),
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Assignment.Status.SUBMITTED)

        review_url = reverse("therapist_review", kwargs={"pk": pk})
        r = self.thr_client.post(review_url, {"comment": "Всё в порядке"})
        self.assertEqual(r.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Assignment.Status.REVIEWED)

        r = self.emp_client.get(detail)
        self.assertContains(r, "Проверено")
        self.assertContains(r, "Всё в порядке")
        self.assertNotContains(r, "Отправить анкету")

    def test_submit_requires_visible_answers(self):
        pk = self.assignment.pk
        submit_url = reverse("employee_assignment_submit", kwargs={"pk": pk})
        r = self.emp_client.post(
            submit_url,
            {"answer_demo_smoke": "true", "expected_revision": "0"},
        )
        self.assertEqual(r.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, Assignment.Status.ASSIGNED)


class UiPermissionsTests(TestCase):
    def setUp(self):
        self.org = make_org()
        self.therapist = make_therapist()
        self.employee_a = make_employee(
            username="emp_a", birth_date=date(1985, 1, 1), org=self.org
        )
        self.employee_b = make_employee(
            username="emp_b", birth_date=date(1988, 2, 2), org=self.org
        )
        self.admin = make_admin()
        self.assignment = assign_for(self.employee_a, self.therapist)
        autosave_draft(
            assignment=self.assignment,
            actor=self.employee_a.user,
            answers={"demo_smoke": False, "demo_note": "секрет"},
        )
        self.assignment.refresh_from_db()
        submit_assignment(
            assignment=self.assignment,
            actor=self.employee_a.user,
            answers={"demo_smoke": False, "demo_note": "секрет"},
            expected_revision=self.assignment.draft_revision,
        )

    def test_t11_admin_cannot_read_answers_via_direct_url(self):
        client = Client()
        assert client.login(username="admin1", password="test-pass-not-secret")
        pk = self.assignment.pk
        for name in (
            "employee_assignment_detail",
            "therapist_assignment_detail",
        ):
            url = reverse(name, kwargs={"pk": pk})
            r = client.get(url)
            self.assertIn(r.status_code, (403, 302))
            if r.status_code == 200:
                self.assertNotContains(r, "секрет")

    def test_t12_cross_employee_forbidden(self):
        client = Client()
        assert client.login(username="emp_b", password="test-pass-not-secret")
        url = reverse(
            "employee_assignment_detail", kwargs={"pk": self.assignment.pk}
        )
        r = client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_t18_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        assert client.login(username="emp_a", password="test-pass-not-secret")
        # Новое назначение для editable POST.
        a2 = assign_for(
            self.employee_a,
            self.therapist,
            due_date=date.today() + timedelta(days=3),
        )
        url = reverse("employee_assignment_autosave", kwargs={"pk": a2.pk})
        r = client.post(url, {"answer_demo_smoke": "false"})
        self.assertEqual(r.status_code, 403)


class TherapistListTests(TestCase):
    def setUp(self):
        self.org = make_org()
        self.therapist = make_therapist()
        self.employee = make_employee(
            username="emp_list", birth_date=date(1992, 3, 3), org=self.org
        )
        self.assignment = assign_for(
            self.employee,
            self.therapist,
            due_date=date.today() - timedelta(days=2),
        )
        self.client = Client()
        assert self.client.login(
            username="therapist1", password="test-pass-not-secret"
        )

    def test_list_filters_and_overdue(self):
        url = reverse("therapist_assignment_list")
        r = self.client.get(url, {"overdue": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Просрочено")
        self.assertContains(r, "emp_list")

        r = self.client.get(url, {"status": Assignment.Status.ASSIGNED})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, str(self.assignment.pk))

    def test_assign_and_cancel_assumption(self):
        list_url = reverse("therapist_assignment_list")
        r = self.client.post(
            reverse("therapist_assign"),
            {
                "employee_id": str(self.employee.pk),
                "due_date": str(date.today() + timedelta(days=5)),
            },
        )
        self.assertEqual(r.status_code, 302)
        new_pk = Assignment.objects.exclude(pk=self.assignment.pk).latest("id").pk

        r = self.client.post(reverse("therapist_cancel", kwargs={"pk": new_pk}))
        self.assertEqual(r.status_code, 302)
        a = Assignment.objects.get(pk=new_pk)
        self.assertEqual(a.status, Assignment.Status.CANCELED)
