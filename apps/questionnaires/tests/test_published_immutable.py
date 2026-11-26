"""Опубликованная версия шаблона неизменяема (пункты и условия)."""
from __future__ import annotations

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.questionnaires.models import QuestionItem, ShowCondition
from apps.questionnaires.services import copy_version_as_draft
from apps.screenings.tests.helpers import (
    assign_for,
    make_employee,
    make_org,
    make_therapist,
    published_version,
)


class PublishedVersionImmutableTests(TestCase):
    def setUp(self):
        self.version = published_version("under_65")
        self.item = self.version.items.get(code="demo_note")
        self.cond = ShowCondition.objects.filter(item__version=self.version).first()

    def test_cannot_save_item_on_published_version(self):
        self.item.text = "попытка изменить опубликованный пункт"
        with self.assertRaises(ValidationError):
            self.item.save()
        self.item.refresh_from_db()
        self.assertNotEqual(self.item.text, "попытка изменить опубликованный пункт")

    def test_cannot_save_condition_on_published_version(self):
        self.assertIsNotNone(self.cond)
        self.cond.value = False
        with self.assertRaises(ValidationError):
            self.cond.save()

    def test_cannot_delete_item_on_published_version(self):
        with self.assertRaises(ValidationError):
            self.item.delete()
        self.assertTrue(QuestionItem.objects.filter(pk=self.item.pk).exists())

    def test_assignment_keeps_version_after_template_copy(self):
        org = make_org()
        therapist = make_therapist()
        employee = make_employee(
            username="emp_freeze",
            birth_date=date(1990, 1, 1),
            org=org,
        )
        assignment = assign_for(
            employee,
            therapist,
            due_date=date.today() + timedelta(days=5),
        )
        frozen_id = assignment.template_version_id
        self.assertEqual(frozen_id, self.version.pk)

        draft = copy_version_as_draft(self.version)
        draft_item = draft.items.get(code="demo_note")
        draft_item.text = "правка только в копии"
        draft_item.save()

        assignment.refresh_from_db()
        self.assertEqual(assignment.template_version_id, frozen_id)
        self.item.refresh_from_db()
        self.assertNotEqual(self.item.text, "правка только в копии")
