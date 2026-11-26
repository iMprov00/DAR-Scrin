"""
Обязательные сценарии матрицы docs/testing.md для этапа 2 (сервисный слой).
Только PostgreSQL. Синтетические данные.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest import mock

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from apps.questionnaires.services import copy_version_as_draft, publish_version
from apps.screenings.models import AnswerSnapshot, Assignment
from apps.screenings.services import (
    DomainError,
    autosave_draft,
    can_view_answers,
    cancel_assignment,
    change_due_date,
    get_answers_for_user,
    is_overdue,
    mark_reviewed,
    return_for_revision,
    submit_assignment,
)
from apps.screenings.tests.helpers import (
    assign_for,
    ensure_published_demo,
    make_admin,
    make_employee,
    make_org,
    make_therapist,
)


class DomainMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_published_demo()
        cls.org = make_org("Орг Тест Матрица")
        cls.therapist = make_therapist("therapist_matrix")
        cls.admin = make_admin("admin_matrix")
        cls.emp_a = make_employee(
            username="emp_a",
            birth_date=date(1990, 1, 1),
            org=cls.org,
        )
        cls.emp_b = make_employee(
            username="emp_b",
            birth_date=date(1985, 6, 1),
            org=cls.org,
        )

    def test_t01_assignment_picks_age_form_on_boundary(self):
        """T01: назначение фиксирует форму по ДР и дате назначения."""
        birth = date(1960, 5, 10)
        emp = make_employee(username="emp_age", birth_date=birth, org=self.org)
        before = assign_for(
            emp, self.therapist, assignment_date=date(2025, 5, 9)
        )
        self.assertEqual(before.age_form, "under_65")
        self.assertEqual(before.template_version.age_form, "under_65")

        emp2 = make_employee(username="emp_age2", birth_date=birth, org=self.org)
        on_day = assign_for(
            emp2, self.therapist, assignment_date=date(2025, 5, 10)
        )
        self.assertEqual(on_day.age_form, "age_65_plus")
        self.assertEqual(on_day.template_version.age_form, "age_65_plus")

    def test_t02_parallel_assignments_isolated(self):
        """T02: два назначения одному сотруднику изолированы."""
        a1 = assign_for(self.emp_a, self.therapist, due_date=date(2030, 1, 10))
        a2 = assign_for(self.emp_a, self.therapist, due_date=date(2030, 2, 10))
        autosave_draft(
            assignment=a1,
            actor=self.emp_a.user,
            answers={"demo_smoke": True, "demo_note": "A1"},
        )
        autosave_draft(
            assignment=a2,
            actor=self.emp_a.user,
            answers={"demo_smoke": False, "demo_note": "A2"},
        )
        a1.refresh_from_db()
        a2.refresh_from_db()
        self.assertEqual(a1.draft_answers["demo_note"], "A1")
        self.assertEqual(a2.draft_answers["demo_note"], "A2")
        self.assertEqual(a1.status, Assignment.Status.DRAFT)
        self.assertEqual(a2.status, Assignment.Status.DRAFT)
        self.assertNotEqual(a1.due_date, a2.due_date)

    def test_t03_edit_after_returned_keeps_old_snapshot(self):
        """T03: после returned можно править; предыдущий снимок неизменяем."""
        assignment = assign_for(self.emp_a, self.therapist)
        submit_assignment(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": True, "demo_pack_years": 5, "demo_note": "v1"},
        )
        assignment.refresh_from_db()
        snap1 = assignment.snapshots.get(sequence=1)
        original = dict(snap1.answers)

        return_for_revision(
            assignment=assignment,
            actor=self.therapist,
            comment="Уточните комментарий",
            new_due_date=assignment.due_date,
        )
        autosave_draft(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_note": "v2"},
        )
        submit_assignment(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": True, "demo_pack_years": 7, "demo_note": "v2"},
        )
        assignment.refresh_from_db()
        snap1.refresh_from_db()
        self.assertEqual(snap1.answers, original)
        self.assertEqual(assignment.snapshots.count(), 2)
        self.assertEqual(assignment.snapshots.get(sequence=2).answers["demo_note"], "v2")

    def test_t04_no_edit_after_reviewed(self):
        """T04: после reviewed autosave отклоняется."""
        assignment = assign_for(self.emp_a, self.therapist)
        submit_assignment(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": False, "demo_note": "ok"},
        )
        mark_reviewed(assignment=assignment, actor=self.therapist, comment="Всё верно")
        with self.assertRaises(DomainError):
            autosave_draft(
                assignment=assignment,
                actor=self.emp_a.user,
                answers={"demo_note": "late"},
            )

    def test_t06_published_version_frozen_on_assignment(self):
        """T06: назначение хранит ту же версию после копии шаблона."""
        assignment = assign_for(self.emp_a, self.therapist)
        version_id = assignment.template_version_id
        draft_copy = copy_version_as_draft(assignment.template_version)
        draft_copy.items.filter(code="demo_note").update(text="[ДЕМО] изменённый текст")
        publish_version(draft_copy)
        assignment.refresh_from_db()
        self.assertEqual(assignment.template_version_id, version_id)
        self.assertNotEqual(assignment.template_version_id, draft_copy.pk)

    def test_t07_hidden_answers_not_in_new_snapshot(self):
        """T07: скрытые ответы не в новом снимке; прошлый снимок цел."""
        assignment = assign_for(self.emp_a, self.therapist)
        submit_assignment(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": True, "demo_pack_years": 10, "demo_note": "first"},
        )
        snap1 = assignment.snapshots.get(sequence=1)
        self.assertIn("demo_pack_years", snap1.answers)

        return_for_revision(
            assignment=assignment,
            actor=self.therapist,
            comment="Пересмотрите курение",
            new_due_date=assignment.due_date + timedelta(days=3),
        )
        # Управляющий ответ False — pack_years скрыт, но в черновике может остаться.
        autosave_draft(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": False, "demo_pack_years": 10, "demo_note": "second"},
        )
        submit_assignment(assignment=assignment, actor=self.emp_a.user)
        snap1.refresh_from_db()
        snap2 = assignment.snapshots.get(sequence=2)
        self.assertEqual(snap1.answers["demo_pack_years"], 10)
        self.assertNotIn("demo_pack_years", snap2.answers)
        self.assertEqual(snap2.answers.get("demo_smoke"), False)

    def test_t08_atomic_submit_rolls_back_on_error(self):
        """T08: при ошибке нет полуотправленного состояния."""
        assignment = assign_for(self.emp_a, self.therapist)
        autosave_draft(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": False},
        )
        assignment.refresh_from_db()
        rev_before = assignment.draft_revision

        with mock.patch(
            "apps.screenings.services.assignments.AnswerSnapshot.objects.create",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                submit_assignment(assignment=assignment, actor=self.emp_a.user)

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, Assignment.Status.DRAFT)
        self.assertEqual(assignment.draft_revision, rev_before)
        self.assertEqual(assignment.snapshots.count(), 0)

    def test_t09_late_autosave_after_submit_rejected(self):
        """T09: поздний autosave не портит снимок и статус."""
        assignment = assign_for(self.emp_a, self.therapist)
        submit_assignment(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": True, "demo_pack_years": 1, "demo_note": "sent"},
        )
        snap = assignment.snapshots.get()
        original = dict(snap.answers)
        with self.assertRaises(DomainError):
            autosave_draft(
                assignment=assignment,
                actor=self.emp_a.user,
                answers={"demo_note": "tamper"},
            )
        assignment.refresh_from_db()
        snap.refresh_from_db()
        self.assertEqual(assignment.status, Assignment.Status.SUBMITTED)
        self.assertEqual(snap.answers, original)

    def test_t11_admin_cannot_read_answers(self):
        """T11: админ без полномочия не читает ответы."""
        assignment = assign_for(self.emp_a, self.therapist)
        submit_assignment(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": False, "demo_note": "secret"},
        )
        self.assertFalse(can_view_answers(self.admin, assignment))
        with self.assertRaises(PermissionDenied):
            get_answers_for_user(self.admin, assignment)

    def test_t12_cross_employee_denied(self):
        """T12: сотрудник A не пишет назначение B."""
        assignment_b = assign_for(self.emp_b, self.therapist)
        with self.assertRaises(PermissionDenied):
            autosave_draft(
                assignment=assignment_b,
                actor=self.emp_a.user,
                answers={"demo_note": "hack"},
            )
        with self.assertRaises(PermissionDenied):
            get_answers_for_user(self.emp_a.user, assignment_b)

    def test_t13_illegal_transition_rejected(self):
        """T13: недопустимый переход отвергается."""
        assignment = assign_for(self.emp_a, self.therapist)
        with self.assertRaises(DomainError):
            mark_reviewed(assignment=assignment, actor=self.therapist)

    def test_t14_overdue_inclusive_due_date(self):
        """T14: в день срока не просрочено; со следующего дня — да."""
        assignment = assign_for(
            self.emp_a, self.therapist, due_date=date(2030, 6, 1)
        )
        self.assertFalse(is_overdue(assignment, today=date(2030, 6, 1)))
        self.assertTrue(is_overdue(assignment, today=date(2030, 6, 2)))
        submit_assignment(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": False},
        )
        assignment.refresh_from_db()
        self.assertFalse(is_overdue(assignment, today=date(2030, 6, 10)))

    def test_t15_return_requires_comment(self):
        """T15: без комментария возврат невозможен; комментарий сохраняется."""
        assignment = assign_for(self.emp_a, self.therapist)
        submit_assignment(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": False},
        )
        with self.assertRaises(DomainError):
            return_for_revision(
                assignment=assignment,
                actor=self.therapist,
                comment="   ",
                new_due_date=assignment.due_date,
            )
        returned = return_for_revision(
            assignment=assignment,
            actor=self.therapist,
            comment="Нужно уточнение",
            new_due_date=assignment.due_date,
        )
        self.assertEqual(returned.status, Assignment.Status.RETURNED)
        self.assertEqual(returned.return_comment, "Нужно уточнение")

    def test_t15a_return_requires_new_due_date_assumption(self):
        """T15a (допущение): new_due_date обязателен при вызове сервиса."""
        assignment = assign_for(self.emp_a, self.therapist)
        submit_assignment(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": False},
        )
        # Явная та же дата допускается.
        returned = return_for_revision(
            assignment=assignment,
            actor=self.therapist,
            comment="Повтор",
            new_due_date=assignment.due_date,
        )
        self.assertEqual(returned.due_date_audits.filter(reason="return").count(), 1)

    def test_t16_cancel_assumption_no_hard_delete(self):
        """T16 (допущение): отмена до reviewed с аудитом, без удаления."""
        assignment = assign_for(self.emp_a, self.therapist)
        pk = assignment.pk
        cancel_assignment(assignment=assignment, actor=self.therapist)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, Assignment.Status.CANCELED)
        self.assertTrue(Assignment.objects.filter(pk=pk).exists())

    def test_t19_due_date_audit(self):
        """T19: аудит смены срока — кто/когда/старое/новое/назначение."""
        assignment = assign_for(
            self.emp_a, self.therapist, due_date=date(2030, 7, 1)
        )
        change_due_date(
            assignment=assignment,
            actor=self.therapist,
            new_due_date=date(2030, 7, 15),
        )
        audit = assignment.due_date_audits.get(reason="manual")
        self.assertEqual(audit.old_due_date, date(2030, 7, 1))
        self.assertEqual(audit.new_due_date, date(2030, 7, 15))
        self.assertEqual(audit.changed_by_id, self.therapist.pk)
        self.assertEqual(audit.assignment_id, assignment.pk)

    def test_snapshot_immutable_save(self):
        assignment = assign_for(self.emp_a, self.therapist)
        submit_assignment(
            assignment=assignment,
            actor=self.emp_a.user,
            answers={"demo_smoke": False},
        )
        snap = AnswerSnapshot.objects.get(assignment=assignment)
        with self.assertRaises(ValueError):
            snap.answers = {"demo_smoke": True}
            snap.save()
