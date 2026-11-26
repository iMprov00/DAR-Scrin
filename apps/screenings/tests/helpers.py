"""Синтетические фабрики для доменных тестов (без реальных ПДн)."""
from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model

from apps.directory.models import Department, EmployeeProfile, Organization
from apps.questionnaires.management.commands.load_demo_questionnaire import (
    ensure_demo_questionnaire,
)
from apps.questionnaires.models import QuestionnaireVersion
from apps.screenings.services import assign_questionnaire

User = get_user_model()


def make_org(name: str = "ООО Тест") -> Organization:
    return Organization.objects.create(name=name)


def make_user(username: str, **flags) -> User:
    user = User.objects.create_user(username=username, password="test-pass-not-secret")
    for key, value in flags.items():
        setattr(user, key, value)
    user.save()
    return user


def make_employee(
    *,
    username: str,
    birth_date: date,
    org: Organization | None = None,
) -> EmployeeProfile:
    org = org or make_org()
    dept = Department.objects.create(organization=org, name="Тестовое подразделение")
    user = make_user(username, is_employee=True)
    return EmployeeProfile.objects.create(
        user=user,
        organization=org,
        department=dept,
        birth_date=birth_date,
    )


def make_therapist(username: str = "therapist1") -> User:
    return make_user(username, is_therapist=True)


def make_admin(username: str = "admin1") -> User:
    return make_user(username, is_org_admin=True, is_staff=True)


def ensure_published_demo() -> None:
    ensure_demo_questionnaire()


def assign_for(
    employee: EmployeeProfile,
    therapist: User,
    *,
    due_date: date | None = None,
    assignment_date: date | None = None,
):
    ensure_published_demo()
    return assign_questionnaire(
        employee=employee,
        due_date=due_date or (date.today() + timedelta(days=7)),
        actor=therapist,
        assignment_date=assignment_date,
    )


def published_version(age_form: str) -> QuestionnaireVersion:
    ensure_published_demo()
    return QuestionnaireVersion.objects.filter(
        age_form=age_form,
        status=QuestionnaireVersion.Status.PUBLISHED,
    ).latest("version_number")
