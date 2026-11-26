"""Раздел «Сотрудники» для is_org_admin без is_staff."""
from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.directory.models import Department, EmployeeProfile, Organization
from apps.screenings.tests.helpers import assign_for, make_employee, make_therapist

User = get_user_model()


class StaffUiTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Орг для сотрудников")
        self.dept = Department.objects.create(
            organization=self.org, name="Отдел кадров"
        )
        self.admin = User.objects.create_user(
            username="org_admin_ui",
            password="test-pass-not-secret",
            is_org_admin=True,
            is_staff=False,
            is_superuser=False,
        )
        self.client = Client()
        assert self.client.login(
            username="org_admin_ui", password="test-pass-not-secret"
        )

    def test_org_admin_creates_employee_without_staff(self):
        url = reverse("employee_staff_create")
        r = self.client.post(
            url,
            {
                "last_name": "Иванов",
                "first_name": "Иван",
                "username": "ivanov_i",
                "birth_date": "1991-03-15",
                "department": str(self.dept.pk),
                "is_employee": "on",
                "is_active": "on",
                "temporary_password": "temp123",
            },
        )
        self.assertEqual(r.status_code, 302)
        user = User.objects.get(username="ivanov_i")
        self.assertTrue(user.is_employee)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.must_change_password)
        profile = EmployeeProfile.objects.get(user=user)
        self.assertEqual(profile.birth_date, date(1991, 3, 15))
        self.assertEqual(profile.department_id, self.dept.pk)

    def test_non_admin_forbidden(self):
        emp = make_employee(username="emp_only", birth_date=date(1990, 1, 1))
        client = Client()
        assert client.login(username="emp_only", password="test-pass-not-secret")
        r = client.get(reverse("employee_staff_list"))
        self.assertEqual(r.status_code, 403)

    def test_org_admin_list_has_no_answers(self):
        therapist = make_therapist("thr_staff")
        emp = make_employee(
            username="emp_listed", birth_date=date(1988, 5, 5), org=self.org
        )
        assignment = assign_for(emp, therapist)
        from apps.screenings.services import autosave_draft, submit_assignment

        autosave_draft(
            assignment=assignment,
            actor=emp.user,
            answers={"demo_smoke": False, "demo_note": "секрет-не-для-админа"},
        )
        assignment.refresh_from_db()
        submit_assignment(
            assignment=assignment,
            actor=emp.user,
            answers={"demo_smoke": False, "demo_note": "секрет-не-для-админа"},
            expected_revision=assignment.draft_revision,
        )
        r = self.client.get(reverse("employee_staff_list"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "секрет-не-для-админа")
        self.assertContains(r, "emp_listed")
