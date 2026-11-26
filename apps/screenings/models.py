"""Обследования: контейнер, назначения, черновики, снимки, аудит срока."""
from django.conf import settings
from django.db import models


class Screening(models.Model):
    """
    Контейнер обследования — точка расширения под будущие разделы
    (медосмотр, итог) без реализации этих разделов в MVP.
    """

    employee = models.ForeignKey(
        "directory.EmployeeProfile",
        on_delete=models.PROTECT,
        related_name="screenings",
        verbose_name="сотрудник",
    )
    organization = models.ForeignKey(
        "directory.Organization",
        on_delete=models.PROTECT,
        related_name="screenings",
        verbose_name="организация",
    )
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "обследование"
        verbose_name_plural = "обследования"

    def __str__(self) -> str:
        return f"Обследование #{self.pk} — {self.employee}"


class Assignment(models.Model):
    """Назначение анкеты. Версия шаблона и age_form фиксируются и не пересчитываются."""

    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Назначено"
        DRAFT = "draft", "Черновик"
        SUBMITTED = "submitted", "Отправлено"
        RETURNED = "returned", "Возвращено"
        REVIEWED = "reviewed", "Проверено"
        CANCELED = "canceled", "Отменено"

    screening = models.ForeignKey(
        Screening,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="обследование",
    )
    template_version = models.ForeignKey(
        "questionnaires.QuestionnaireVersion",
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name="версия шаблона",
    )
    # Зафиксированная форма на дату назначения (не пересчитывается).
    age_form = models.CharField("форма возраста", max_length=20)
    due_date = models.DateField("срок")
    status = models.CharField(
        "статус",
        max_length=20,
        choices=Status.choices,
        default=Status.ASSIGNED,
    )
    draft_answers = models.JSONField("черновик ответов", default=dict, blank=True)
    draft_revision = models.PositiveIntegerField(
        "ревизия черновика",
        default=0,
        help_text="Для отклонения устаревшего autosave после submit (гонка).",
    )
    return_comment = models.TextField("комментарий возврата", blank=True, default="")
    review_comment = models.TextField("комментарий проверки", blank=True, default="")
    reviewed_at = models.DateTimeField("проверено в", null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_assignments",
        verbose_name="назначил",
        null=True,
        blank=True,
    )
    assigned_at = models.DateTimeField("назначено", auto_now_add=True)
    updated_at = models.DateTimeField("обновлено", auto_now=True)

    class Meta:
        verbose_name = "назначение"
        verbose_name_plural = "назначения"
        ordering = ["-assigned_at"]

    def __str__(self) -> str:
        return f"Назначение #{self.pk} [{self.status}] до {self.due_date}"


class AnswerSnapshot(models.Model):
    """Неизменяемый снимок ответов при успешной отправке."""

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="snapshots",
        verbose_name="назначение",
    )
    answers = models.JSONField("ответы")
    sequence = models.PositiveIntegerField("номер снимка")
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "снимок ответов"
        verbose_name_plural = "снимки ответов"
        ordering = ["assignment_id", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "sequence"],
                name="uniq_snapshot_sequence_per_assignment",
            ),
        ]

    def __str__(self) -> str:
        return f"Снимок #{self.sequence} назначения {self.assignment_id}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError(
                "Снимок ответов неизменяем (docs/workflow.md). "
                "Нельзя обновлять существующую запись."
            )
        return super().save(*args, **kwargs)


class DueDateAudit(models.Model):
    """Аудит смены срока: кто/когда/старое/новое/назначение. Без содержания ответов."""

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="due_date_audits",
        verbose_name="назначение",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="due_date_audits",
        verbose_name="изменил",
    )
    old_due_date = models.DateField("старый срок")
    new_due_date = models.DateField("новый срок")
    changed_at = models.DateTimeField("когда", auto_now_add=True)
    reason = models.CharField(
        "причина",
        max_length=64,
        blank=True,
        default="",
        help_text="Например return или manual — без тел ответов.",
    )

    class Meta:
        verbose_name = "аудит срока"
        verbose_name_plural = "аудит сроков"
        ordering = ["-changed_at"]

    def __str__(self) -> str:
        return (
            f"Срок назначения {self.assignment_id}: "
            f"{self.old_due_date} → {self.new_due_date}"
        )


class ActionAudit(models.Model):
    """Журнал значимых действий без содержания ответов."""

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="action_audits",
        verbose_name="назначение",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="action_audits",
        verbose_name="кто",
        null=True,
        blank=True,
    )
    action = models.CharField("действие", max_length=64)
    details = models.JSONField("детали", default=dict, blank=True)
    created_at = models.DateTimeField("когда", auto_now_add=True)

    class Meta:
        verbose_name = "запись журнала"
        verbose_name_plural = "журнал действий"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} @ {self.created_at}"
