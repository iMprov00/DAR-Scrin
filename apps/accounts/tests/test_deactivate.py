"""T05: неактивный пользователь — вход запрещён, сессии сброшены, история сохранена."""
from datetime import date

from django.contrib.sessions.backends.db import SessionStore
from django.test import Client, TestCase

from apps.accounts.models import User
from apps.accounts.services import deactivate_user
from apps.screenings.models import Assignment
from apps.screenings.tests.helpers import assign_for, make_employee, make_therapist


class DeactivateUserTests(TestCase):
    def test_deactivate_clears_sessions_keeps_user_row(self):
        """T05: сессии сбрасываются, строка пользователя остаётся."""
        user = make_employee(
            username="to_deactivate",
            birth_date=date(1990, 1, 1),
        ).user
        store = SessionStore()
        store["_auth_user_id"] = str(user.pk)
        store.create()
        session_key = store.session_key

        deactivate_user(user)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertFalse(SessionStore().exists(session_key))

    def test_t05_inactive_login_forbidden(self):
        """T05: после деактивации вход не проходит."""
        user = make_employee(
            username="inactive_login",
            birth_date=date(1991, 2, 2),
        ).user
        deactivate_user(user)

        client = Client()
        logged_in = client.login(
            username="inactive_login",
            password="test-pass-not-secret",
        )
        self.assertFalse(logged_in)
        self.assertNotIn("_auth_user_id", client.session)

    def test_t05_assignment_history_preserved(self):
        """T05: история назначений после деактивации не удаляется."""
        therapist = make_therapist("therapist_t05")
        employee = make_employee(
            username="emp_t05_hist",
            birth_date=date(1988, 5, 5),
        )
        assignment = assign_for(employee, therapist)
        assignment_pk = assignment.pk
        status_before = assignment.status
        user_pk = employee.user_id

        deactivate_user(employee.user)

        self.assertTrue(User.objects.filter(pk=user_pk, is_active=False).exists())
        preserved = Assignment.objects.select_related("screening").get(
            pk=assignment_pk
        )
        self.assertEqual(preserved.status, status_before)
        self.assertEqual(preserved.screening.employee_id, employee.pk)
