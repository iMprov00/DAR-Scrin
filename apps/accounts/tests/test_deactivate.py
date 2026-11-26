"""Деактивация со сбросом сессий (дух T05 на уровне сервиса)."""
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase

from apps.accounts.services import deactivate_user
from apps.screenings.tests.helpers import make_user


class DeactivateUserTests(TestCase):
    def test_deactivate_clears_sessions_keeps_user_row(self):
        user = make_user("to_deactivate", is_employee=True)
        store = SessionStore()
        store["_auth_user_id"] = str(user.pk)
        store.create()
        session_key = store.session_key

        deactivate_user(user)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertFalse(SessionStore().exists(session_key))
