"""Шаблоны анкет, версии, пункты и условия показа."""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class QuestionnaireTemplate(models.Model):
    """
    Шаблон анкеты.
    is_demo=True — явно демонстрационный шаблон, НЕ официальная анкета Минздрава.
    """

    name = models.CharField("название", max_length=255)
    is_demo = models.BooleanField(
        "демонстрационный",
        default=False,
        help_text=(
            "Демо-шаблон для разработки. Не подменяет официальную анкету Минздрава РФ. "
            "Формулировки — синтетические."
        ),
    )
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "шаблон анкеты"
        verbose_name_plural = "шаблоны анкет"

    def __str__(self) -> str:
        suffix = " [ДЕМО]" if self.is_demo else ""
        return f"{self.name}{suffix}"


class QuestionnaireVersion(models.Model):
    """Версия шаблона. published — неизменяема; правки через копию (draft)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликовано"

    class AgeForm(models.TextChoices):
        UNDER_65 = "under_65", "До 65 лет"
        AGE_65_PLUS = "age_65_plus", "65 лет и старше"

    template = models.ForeignKey(
        QuestionnaireTemplate,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="шаблон",
    )
    status = models.CharField(
        "статус",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    age_form = models.CharField(
        "возрастная форма",
        max_length=20,
        choices=AgeForm.choices,
    )
    version_number = models.PositiveIntegerField("номер версии", default=1)
    published_at = models.DateTimeField("опубликована", null=True, blank=True)
    created_at = models.DateTimeField("создана", auto_now_add=True)

    class Meta:
        verbose_name = "версия шаблона"
        verbose_name_plural = "версии шаблонов"
        ordering = ["template_id", "age_form", "-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "age_form", "version_number"],
                name="uniq_template_age_form_version",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.template} / {self.get_age_form_display()} "
            f"v{self.version_number} ({self.status})"
        )

    @property
    def is_immutable(self) -> bool:
        return self.status == self.Status.PUBLISHED

    def clean(self) -> None:
        if self.pk and self.is_immutable:
            original = QuestionnaireVersion.objects.filter(pk=self.pk).first()
            if original and original.is_immutable:
                raise ValidationError(
                    "Опубликованная версия неизменяема. Правки — через копию "
                    "(docs/architecture.md)."
                )


class QuestionItem(models.Model):
    """Пункт анкеты со стабильным кодом."""

    class AnswerType(models.TextChoices):
        YES_NO = "yes_no", "Да/нет"
        NUMBER = "number", "Число"
        TEXT = "text", "Текст"
        SINGLE_CHOICE = "single_choice", "Один вариант"

    version = models.ForeignKey(
        QuestionnaireVersion,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="версия",
    )
    code = models.SlugField("код", max_length=64)
    text = models.TextField("текст пункта")
    answer_type = models.CharField(
        "тип ответа",
        max_length=20,
        choices=AnswerType.choices,
    )
    # Для single_choice: [{"value": "a", "label": "..."}, ...]
    choices = models.JSONField("варианты", default=list, blank=True)
    sort_order = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "пункт анкеты"
        verbose_name_plural = "пункты анкеты"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "code"],
                name="uniq_question_code_per_version",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.text[:60]}"


class ShowCondition(models.Model):
    """Условие показа пункта (в БД). Простой оператор eq по значению управляющего пункта."""

    class Operator(models.TextChoices):
        EQ = "eq", "Равно"

    item = models.ForeignKey(
        QuestionItem,
        on_delete=models.CASCADE,
        related_name="show_conditions",
        verbose_name="зависимый пункт",
    )
    source_item = models.ForeignKey(
        QuestionItem,
        on_delete=models.CASCADE,
        related_name="controls_conditions",
        verbose_name="управляющий пункт",
    )
    operator = models.CharField(
        "оператор",
        max_length=10,
        choices=Operator.choices,
        default=Operator.EQ,
    )
    value = models.JSONField("ожидаемое значение")

    class Meta:
        verbose_name = "условие показа"
        verbose_name_plural = "условия показа"

    def __str__(self) -> str:
        return f"{self.item.code} if {self.source_item.code} {self.operator} {self.value}"
