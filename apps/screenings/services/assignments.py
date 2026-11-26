"""
Сервисный слой назначений: переходы, autosave, submit, возврат, проверка.
Переходы — docs/workflow.md. Допущения (отмена, новый срок при возврате,
допустимые статусы смены срока) — docs/decisions.md, помечены в коде.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.directory.models import EmployeeProfile
from apps.directory.services.age import select_age_form
from apps.questionnaires.models import QuestionnaireVersion
from apps.questionnaires.services.visibility import filter_visible_answers
from apps.screenings.models import (
    ActionAudit,
    AnswerSnapshot,
    Assignment,
    DueDateAudit,
    Screening,
)
from apps.screenings.services.events import emit
from apps.screenings.services.permissions import (
    can_fill_assignment,
    can_manage_assignment,
    can_view_answers,
)

# Согласованное ядро переходов (docs/workflow.md).
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    Assignment.Status.ASSIGNED: {
        Assignment.Status.DRAFT,
        Assignment.Status.SUBMITTED,
        Assignment.Status.CANCELED,  # допущение docs/decisions.md п.5
    },
    Assignment.Status.DRAFT: {
        Assignment.Status.SUBMITTED,
        Assignment.Status.CANCELED,  # допущение
    },
    Assignment.Status.SUBMITTED: {
        Assignment.Status.RETURNED,
        Assignment.Status.REVIEWED,
        Assignment.Status.CANCELED,  # допущение
    },
    Assignment.Status.RETURNED: {
        Assignment.Status.SUBMITTED,
        Assignment.Status.CANCELED,  # допущение
    },
    Assignment.Status.REVIEWED: set(),
    Assignment.Status.CANCELED: set(),
}

EDITABLE_STATUSES = {
    Assignment.Status.ASSIGNED,
    Assignment.Status.DRAFT,
    Assignment.Status.RETURNED,
}

# Допущение docs/decisions.md п.6: смена срока в assigned/draft/returned;
# submitted — не разрешаем до отдельного решения.
DUE_DATE_CHANGE_STATUSES = {
    Assignment.Status.ASSIGNED,
    Assignment.Status.DRAFT,
    Assignment.Status.RETURNED,
}


class DomainError(ValidationError):
    """Доменная ошибка без изменения состояния."""


def _ensure_transition(current: str, target: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise DomainError(
            f"Недопустимый переход статуса: {current} → {target} "
            f"(docs/workflow.md)."
        )


def _lock_assignment(assignment_id: int) -> Assignment:
    return (
        Assignment.objects.select_for_update()
        .select_related(
            "screening",
            "screening__employee",
            "screening__employee__user",
            "template_version",
            "template_version__template",
        )
        .get(pk=assignment_id)
    )


@transaction.atomic
def assign_questionnaire(
    *,
    employee: EmployeeProfile,
    due_date: date,
    actor: User,
    template: Any | None = None,
    assignment_date: date | None = None,
) -> Assignment:
    """Создаёт контейнер (при необходимости) и назначение с зафиксированной формой."""
    if not actor.is_therapist:
        raise PermissionDenied("Назначать анкету может только терапевт.")

    on_date = assignment_date or timezone.localdate()
    age_form = select_age_form(employee.birth_date, on_date).value

    version_qs = QuestionnaireVersion.objects.filter(
        status=QuestionnaireVersion.Status.PUBLISHED,
        age_form=age_form,
    )
    if template is not None:
        from apps.questionnaires.models import QuestionnaireTemplate

        if isinstance(template, QuestionnaireTemplate):
            version_qs = version_qs.filter(template=template)
        elif isinstance(template, QuestionnaireVersion):
            version_qs = version_qs.filter(template=template.template)
    version = version_qs.order_by("-version_number", "-published_at").first()
    if version is None:
        raise DomainError(
            f"Нет опубликованной версии шаблона для формы {age_form}."
        )

    screening = Screening.objects.create(
        employee=employee,
        organization=employee.organization,
    )
    assignment = Assignment.objects.create(
        screening=screening,
        template_version=version,
        age_form=age_form,
        due_date=due_date,
        status=Assignment.Status.ASSIGNED,
        assigned_by=actor,
    )
    ActionAudit.objects.create(
        assignment=assignment,
        actor=actor,
        action="assigned",
        details={"age_form": age_form, "version_id": version.pk},
    )
    emit("assigned", assignment_id=assignment.pk, actor_id=actor.pk)
    return assignment


@transaction.atomic
def autosave_draft(
    *,
    assignment: Assignment,
    actor: User,
    answers: dict[str, Any],
    expected_revision: int | None = None,
) -> Assignment:
    """Автосохранение черновика. После submit/reviewed/canceled — отказ."""
    locked = _lock_assignment(assignment.pk)
    if not can_fill_assignment(actor, locked):
        raise PermissionDenied("Нет права заполнять это назначение.")
    if locked.status not in EDITABLE_STATUSES:
        raise DomainError(
            f"Автосохранение запрещено в статусе {locked.status}."
        )
    if expected_revision is not None and expected_revision != locked.draft_revision:
        raise DomainError(
            "Устаревшая ревизия черновика: сохранение отклонено (гонка)."
        )

    if locked.status == Assignment.Status.ASSIGNED:
        _ensure_transition(locked.status, Assignment.Status.DRAFT)
        locked.status = Assignment.Status.DRAFT

    # Ответы мержатся в черновик; скрытые значения не стираются из черновика.
    merged = dict(locked.draft_answers or {})
    merged.update(answers)
    locked.draft_answers = merged
    locked.draft_revision = locked.draft_revision + 1
    locked.save(
        update_fields=["status", "draft_answers", "draft_revision", "updated_at"]
    )
    return locked


@transaction.atomic
def submit_assignment(
    *,
    assignment: Assignment,
    actor: User,
    answers: dict[str, Any] | None = None,
    expected_revision: int | None = None,
) -> Assignment:
    """
    Атомарная отправка: снимок видимых ответов + статус submitted,
    либо без изменений при ошибке (T08).
    """
    locked = _lock_assignment(assignment.pk)
    if not can_fill_assignment(actor, locked):
        raise PermissionDenied("Нет права отправлять это назначение.")

    target = Assignment.Status.SUBMITTED
    _ensure_transition(locked.status, target)

    if expected_revision is not None and expected_revision != locked.draft_revision:
        raise DomainError(
            "Устаревшая ревизия черновика: отправка отклонена (гонка)."
        )

    draft = dict(locked.draft_answers or {})
    if answers is not None:
        draft.update(answers)

    visible = filter_visible_answers(locked.template_version, draft)
    # Пустой ответ ≠ «нет» — не подставляем False за отсутствующие ключи.

    next_seq = (
        locked.snapshots.order_by("-sequence").values_list("sequence", flat=True).first()
        or 0
    ) + 1

    AnswerSnapshot.objects.create(
        assignment=locked,
        answers=visible,
        sequence=next_seq,
    )
    locked.draft_answers = draft
    locked.status = target
    locked.draft_revision = locked.draft_revision + 1
    locked.save(
        update_fields=["draft_answers", "status", "draft_revision", "updated_at"]
    )
    ActionAudit.objects.create(
        assignment=locked,
        actor=actor,
        action="submitted",
        details={"snapshot_sequence": next_seq},
    )
    emit("submitted", assignment_id=locked.pk, actor_id=actor.pk)
    return locked


@transaction.atomic
def return_for_revision(
    *,
    assignment: Assignment,
    actor: User,
    comment: str,
    new_due_date: date,
) -> Assignment:
    """
    Возврат submitted → returned.
    Согласовано: комментарий обязателен.
    Допущение docs/decisions.md п.4: новый срок обязателен (может совпасть с прежним).
    """
    locked = _lock_assignment(assignment.pk)
    if not can_manage_assignment(actor, locked):
        raise PermissionDenied("Возврат доступен только терапевту.")

    _ensure_transition(locked.status, Assignment.Status.RETURNED)

    cleaned = (comment or "").strip()
    if not cleaned:
        raise DomainError("Комментарий врача при возврате обязателен.")

    if new_due_date is None:
        # Допущение T15a / decisions.md п.4.
        raise DomainError(
            "При возврате обязателен новый срок "
            "(допущение docs/decisions.md п.4; дата может совпасть с прежней)."
        )

    old_due = locked.due_date
    locked.status = Assignment.Status.RETURNED
    locked.return_comment = cleaned
    locked.due_date = new_due_date
    locked.save(
        update_fields=["status", "return_comment", "due_date", "updated_at"]
    )

    # Аудит срока при возврате (даже если дата явно та же) — допущение п.4.
    DueDateAudit.objects.create(
        assignment=locked,
        changed_by=actor,
        old_due_date=old_due,
        new_due_date=new_due_date,
        reason="return",
    )

    ActionAudit.objects.create(
        assignment=locked,
        actor=actor,
        action="returned",
        details={"has_comment": True},
    )
    emit("returned", assignment_id=locked.pk, actor_id=actor.pk)
    return locked


@transaction.atomic
def mark_reviewed(
    *,
    assignment: Assignment,
    actor: User,
    comment: str = "",
) -> Assignment:
    locked = _lock_assignment(assignment.pk)
    if not can_manage_assignment(actor, locked):
        raise PermissionDenied("Отметку «Проверено» ставит терапевт.")

    _ensure_transition(locked.status, Assignment.Status.REVIEWED)
    locked.status = Assignment.Status.REVIEWED
    locked.review_comment = (comment or "").strip()
    locked.reviewed_at = timezone.now()
    locked.save(
        update_fields=["status", "review_comment", "reviewed_at", "updated_at"]
    )
    ActionAudit.objects.create(
        assignment=locked,
        actor=actor,
        action="reviewed",
        details={},
    )
    emit("reviewed", assignment_id=locked.pk, actor_id=actor.pk)
    return locked


@transaction.atomic
def cancel_assignment(*, assignment: Assignment, actor: User) -> Assignment:
    """
    Отмена до reviewed — допущение docs/decisions.md п.5 / docs/workflow.md.
    Без жёсткого удаления записей.
    """
    locked = _lock_assignment(assignment.pk)
    if not can_manage_assignment(actor, locked):
        raise PermissionDenied("Отмена доступна только терапевту.")

    _ensure_transition(locked.status, Assignment.Status.CANCELED)
    locked.status = Assignment.Status.CANCELED
    locked.save(update_fields=["status", "updated_at"])
    ActionAudit.objects.create(
        assignment=locked,
        actor=actor,
        action="canceled",
        details={"assumption": "docs/decisions.md#5"},
    )
    return locked


@transaction.atomic
def change_due_date(
    *,
    assignment: Assignment,
    actor: User,
    new_due_date: date,
) -> Assignment:
    """
    Смена срока с аудитом.
    Допущение docs/decisions.md п.6: разрешено в assigned/draft/returned.
    """
    locked = _lock_assignment(assignment.pk)
    if not can_manage_assignment(actor, locked):
        raise PermissionDenied("Смену срока выполняет терапевт.")
    if locked.status not in DUE_DATE_CHANGE_STATUSES:
        raise DomainError(
            f"Смена срока в статусе {locked.status} не разрешена "
            f"(допущение docs/decisions.md п.6)."
        )

    old_due = locked.due_date
    if old_due == new_due_date:
        return locked

    locked.due_date = new_due_date
    locked.save(update_fields=["due_date", "updated_at"])
    DueDateAudit.objects.create(
        assignment=locked,
        changed_by=actor,
        old_due_date=old_due,
        new_due_date=new_due_date,
        reason="manual",
    )
    return locked


def get_answers_for_user(user: User, assignment: Assignment) -> dict[str, Any]:
    """Чтение ответов с объектной проверкой прав (в т.ч. отказ админу).

    В статусах редактирования (assigned/draft/returned) — всегда черновик.
    Когда анкета уже не редактируется — последний неизменяемый снимок.
    """
    if not can_view_answers(user, assignment):
        raise PermissionDenied(
            "Недостаточно прав для чтения ответов назначения."
        )
    if assignment.status in EDITABLE_STATUSES:
        return dict(assignment.draft_answers or {})
    latest = assignment.snapshots.order_by("-sequence").first()
    if latest:
        return dict(latest.answers)
    return dict(assignment.draft_answers or {})
