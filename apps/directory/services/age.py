"""Возраст и выбор формы анкеты (до 65 / 65+) в TIME_ZONE приложения."""
from __future__ import annotations

from datetime import date
from enum import StrEnum

from django.utils import timezone


class AgeForm(StrEnum):
    UNDER_65 = "under_65"
    AGE_65_PLUS = "age_65_plus"


def full_years_on(birth_date: date, on_date: date) -> int:
    """Полные годы на календарную дату on_date (не по часовому поясу браузера)."""
    years = on_date.year - birth_date.year
    if (on_date.month, on_date.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def select_age_form(birth_date: date, on_date: date | None = None) -> AgeForm:
    """
    Выбор формы по полным годам на дату назначения.
    В день исполнения 65 лет — форма 65+ (docs/workflow.md, docs/decisions.md).
    """
    if on_date is None:
        on_date = timezone.localdate()
    years = full_years_on(birth_date, on_date)
    if years >= 65:
        return AgeForm.AGE_65_PLUS
    return AgeForm.UNDER_65
