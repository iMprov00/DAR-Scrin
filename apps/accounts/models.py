"""Пользователи и роли (совмещение ролей допускается)."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Учётная запись. Роли — флаги; одна учётка может совмещать роли."""

    is_employee = models.BooleanField(
        "сотрудник",
        default=False,
        help_text="Роль сотрудника: свои назначения и ответы.",
    )
    is_therapist = models.BooleanField(
        "терапевт",
        default=False,
        help_text="Роль терапевта: назначения и проверка по организации.",
    )
    is_org_admin = models.BooleanField(
        "администратор организации",
        default=False,
        help_text=(
            "Администратор учёток и подразделений. "
            "По умолчанию без доступа к ответам анкет."
        ),
    )
    can_edit_questionnaires = models.BooleanField(
        "правка шаблонов анкет",
        default=False,
        help_text=(
            "Отдельное полномочие на шаблоны в Django Admin; "
            "не выдаётся всем org_admin автоматически."
        ),
    )
    # Допущение docs/decisions.md п.1: обязательная смена пароля при первом входе.
    # UI смены пароля — не этап 2; поле и проверка в сервисе.
    must_change_password = models.BooleanField(
        "обязательна смена пароля",
        default=False,
    )

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
