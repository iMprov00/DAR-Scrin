"""Флаг can_edit_questionnaires реально ограничивает /admin/ шаблонов."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class QuestionnaireAdminFlagTests(TestCase):
    def test_staff_without_flag_denied(self):
        User.objects.create_user(
            username="staff_no_q",
            password="test-pass-not-secret",
            is_staff=True,
            can_edit_questionnaires=False,
        )
        client = Client()
        assert client.login(username="staff_no_q", password="test-pass-not-secret")
        url = reverse("admin:questionnaires_questionnairetemplate_changelist")
        r = client.get(url)
        self.assertIn(r.status_code, (302, 403))

    def test_staff_with_flag_allowed(self):
        User.objects.create_user(
            username="staff_yes_q",
            password="test-pass-not-secret",
            is_staff=True,
            can_edit_questionnaires=True,
        )
        client = Client()
        assert client.login(username="staff_yes_q", password="test-pass-not-secret")
        url = reverse("admin:questionnaires_questionnairetemplate_changelist")
        r = client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_assignment_not_in_admin(self):
        User.objects.create_superuser(
            username="super1",
            email="s@example.com",
            password="test-pass-not-secret",
        )
        client = Client()
        assert client.login(username="super1", password="test-pass-not-secret")
        # Модели ответов/снимков не зарегистрированы.
        with self.assertRaises(Exception):
            reverse("admin:screenings_assignment_changelist")
        with self.assertRaises(Exception):
            reverse("admin:screenings_answersnapshot_changelist")
