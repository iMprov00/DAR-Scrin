"""
Просрочка — вычисляемый признак, не статус.
Допущение docs/decisions.md п.3 / docs/workflow.md: день срока включителен;
просрочка со следующего календарного дня в TIME_ZONE.
"""
from __future__ import annotations

from datetime import date

from django.utils import timezone

from apps.screenings.models import Assignment

_OVERDUE_STATUSES = {
    Assignment.Status.ASSIGNED,
    Assignment.Status.DRAFT,
    Assignment.Status.RETURNED,
}


def is_overdue(assignment: Assignment, today: date | None = None) -> bool:
    if assignment.status not in _OVERDUE_STATUSES:
        return False
    if today is None:
        today = timezone.localdate()
    return today > assignment.due_date
