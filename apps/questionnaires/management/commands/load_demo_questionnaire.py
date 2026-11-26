"""
Загрузка явно помеченного демо-шаблона.
НЕ официальная анкета Минздрава — синтетические формулировки для разработки.
"""
from django.core.management.base import BaseCommand

from apps.questionnaires.models import (
    QuestionItem,
    QuestionnaireTemplate,
    QuestionnaireVersion,
    ShowCondition,
)
from apps.questionnaires.services import publish_version


DEMO_NAME = "ДЕМО: минимальный шаблон (не анкета Минздрава)"


def ensure_demo_questionnaire() -> QuestionnaireTemplate:
    template, _ = QuestionnaireTemplate.objects.get_or_create(
        name=DEMO_NAME,
        defaults={
            "is_demo": True,
        },
    )
    if not template.is_demo:
        template.is_demo = True
        template.save(update_fields=["is_demo"])

    for age_form in (
        QuestionnaireVersion.AgeForm.UNDER_65,
        QuestionnaireVersion.AgeForm.AGE_65_PLUS,
    ):
        if QuestionnaireVersion.objects.filter(
            template=template,
            age_form=age_form,
            status=QuestionnaireVersion.Status.PUBLISHED,
        ).exists():
            continue

        version = QuestionnaireVersion.objects.create(
            template=template,
            status=QuestionnaireVersion.Status.DRAFT,
            age_form=age_form,
            version_number=1,
        )
        q1 = QuestionItem.objects.create(
            version=version,
            code="demo_smoke",
            text="[ДЕМО] Курите ли вы табак? (синтетический пункт)",
            answer_type=QuestionItem.AnswerType.YES_NO,
            sort_order=1,
        )
        q2 = QuestionItem.objects.create(
            version=version,
            code="demo_pack_years",
            text="[ДЕМО] Сколько пачко-лет? (синтетический пункт, условный)",
            answer_type=QuestionItem.AnswerType.NUMBER,
            sort_order=2,
        )
        QuestionItem.objects.create(
            version=version,
            code="demo_note",
            text="[ДЕМО] Комментарий сотрудника (синтетический текст)",
            answer_type=QuestionItem.AnswerType.TEXT,
            sort_order=3,
        )
        ShowCondition.objects.create(
            item=q2,
            source_item=q1,
            operator=ShowCondition.Operator.EQ,
            value=True,
        )
        publish_version(version)

    return template


class Command(BaseCommand):
    help = (
        "Создаёт явно помеченный демо-шаблон (is_demo). "
        "Не является официальной анкетой Минздрава."
    )

    def handle(self, *args, **options):
        template = ensure_demo_questionnaire()
        self.stdout.write(
            self.style.SUCCESS(
                f"Демо-шаблон готов: id={template.pk}, name={template.name!r}, is_demo={template.is_demo}"
            )
        )
