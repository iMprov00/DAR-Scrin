"""Справочник: организация, подразделения, карточки сотрудников."""
from django.conf import settings
from django.db import models


class Organization(models.Model):
    """Организация (MVP — одна)."""

    name = models.CharField("название", max_length=255)

    class Meta:
        verbose_name = "организация"
        verbose_name_plural = "организации"

    def __str__(self) -> str:
        return self.name


class Department(models.Model):
    """Подразделение организации."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="departments",
        verbose_name="организация",
    )
    name = models.CharField("название", max_length=255)

    class Meta:
        verbose_name = "подразделение"
        verbose_name_plural = "подразделения"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class EmployeeProfile(models.Model):
    """Карточка сотрудника. Дата рождения — источник возраста для выбора формы."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        verbose_name="учётная запись",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name="организация",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name="подразделение",
    )
    birth_date = models.DateField("дата рождения")

    class Meta:
        verbose_name = "карточка сотрудника"
        verbose_name_plural = "карточки сотрудников"

    def __str__(self) -> str:
        return f"{self.user.get_username()} ({self.birth_date})"
