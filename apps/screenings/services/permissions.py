"""Объектные права на назначение и ответы (docs/requirements.md)."""
from __future__ import annotations

from apps.accounts.models import User
from apps.screenings.models import Assignment


def can_view_assignment(user: User, assignment: Assignment) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_therapist:
        return True
    if user.is_org_admin:
        # Админ видит факт назначения, но не ответы (см. can_view_answers).
        return True
    if user.is_employee:
        return assignment.screening.employee.user_id == user.pk
    return False


def can_view_answers(user: User, assignment: Assignment) -> bool:
    """
    Администратор по умолчанию НЕ читает ответы, в том числе «по прямой URL»
    (проверка на уровне сервиса — docs/requirements.md, T11).
    """
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_therapist:
        return True
    if user.is_employee and assignment.screening.employee.user_id == user.pk:
        return True
    # is_org_admin без роли терапевта / владельца — отказ.
    return False


def can_manage_assignment(user: User, assignment: Assignment) -> bool:
    """Назначение, срок, возврат, проверка, отмена — терапевт."""
    return bool(
        user.is_authenticated and user.is_active and user.is_therapist
    )


def can_fill_assignment(user: User, assignment: Assignment) -> bool:
    """Заполнение/autosave/submit — только владелец-сотрудник."""
    if not user.is_authenticated or not user.is_active or not user.is_employee:
        return False
    return assignment.screening.employee.user_id == user.pk
