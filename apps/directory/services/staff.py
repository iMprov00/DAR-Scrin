"""Создание и обновление учёток/карточек одним действием (без Django groups)."""
from __future__ import annotations

import secrets
import string
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.services import deactivate_user
from apps.directory.models import Department, EmployeeProfile, Organization

User = get_user_model()


def generate_temporary_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@transaction.atomic
def save_staff_member(
    *,
    actor: User,
    username: str,
    first_name: str,
    last_name: str,
    birth_date: date,
    department: Department | None,
    is_employee: bool,
    is_therapist: bool,
    is_org_admin: bool,
    is_active: bool,
    temporary_password: str | None = None,
    user: User | None = None,
) -> tuple[User, EmployeeProfile, str | None]:
    """
    Учётка + карточка сотрудника одним действием.
    Не выставляет is_staff / is_superuser. Группы Django не используются.
    Возвращает (user, profile, выданный_временный_пароль|None).
    """
    if not actor.is_authenticated or not actor.is_active or not actor.is_org_admin:
        raise PermissionDenied("Раздел «Сотрудники» доступен администратору организации.")

    username = (username or "").strip()
    if not username:
        raise ValidationError({"username": "Укажите логин."})
    if " " in username:
        raise ValidationError(
            {"username": "Логин не может содержать пробелы. ФИО укажите отдельно."}
        )
    if not (is_employee or is_therapist or is_org_admin):
        raise ValidationError("Выберите хотя бы одну роль.")

    org = Organization.objects.order_by("id").first()
    if org is None:
        raise ValidationError("Сначала создайте организацию в служебном разделе.")

    if department is not None and department.organization_id != org.pk:
        raise ValidationError({"department": "Подразделение другой организации."})

    issued_password: str | None = None
    if user is None:
        if User.objects.filter(username=username).exists():
            raise ValidationError({"username": "Такой логин уже занят."})
        if not temporary_password:
            temporary_password = generate_temporary_password()
        user = User(username=username)
        user.set_password(temporary_password)
        issued_password = temporary_password
        user.must_change_password = True
    else:
        if User.objects.filter(username=username).exclude(pk=user.pk).exists():
            raise ValidationError({"username": "Такой логин уже занят."})
        user.username = username
        if temporary_password:
            user.set_password(temporary_password)
            user.must_change_password = True
            issued_password = temporary_password

    user.first_name = (first_name or "").strip()
    user.last_name = (last_name or "").strip()
    user.is_employee = bool(is_employee)
    user.is_therapist = bool(is_therapist)
    user.is_org_admin = bool(is_org_admin)
    # Повседневный org_admin / сотрудник / терапевт — без Django Admin.
    user.is_staff = False
    user.is_superuser = False
    user.is_active = bool(is_active)
    user.save()

    if not is_active:
        # Сброс сессий при отключении (история обследований сохраняется).
        deactivate_user(user)

    profile, _ = EmployeeProfile.objects.update_or_create(
        user=user,
        defaults={
            "organization": org,
            "department": department,
            "birth_date": birth_date,
        },
    )
    return user, profile, issued_password
