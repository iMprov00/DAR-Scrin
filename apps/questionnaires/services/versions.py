"""Публикация и копирование версий шаблона."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.questionnaires.models import (
    QuestionItem,
    QuestionnaireVersion,
    ShowCondition,
)


@transaction.atomic
def publish_version(version: QuestionnaireVersion) -> QuestionnaireVersion:
    """Публикация делает версию неизменяемой."""
    if version.status == QuestionnaireVersion.Status.PUBLISHED:
        return version
    if not version.items.exists():
        raise ValidationError("Нельзя опубликовать версию без пунктов.")
    version.status = QuestionnaireVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.save(update_fields=["status", "published_at"])
    return version


@transaction.atomic
def copy_version_as_draft(version: QuestionnaireVersion) -> QuestionnaireVersion:
    """Правки опубликованной версии — только через новую draft-копию."""
    next_number = (
        QuestionnaireVersion.objects.filter(
            template=version.template,
            age_form=version.age_form,
        )
        .order_by("-version_number")
        .values_list("version_number", flat=True)
        .first()
        or 0
    ) + 1

    new_version = QuestionnaireVersion.objects.create(
        template=version.template,
        status=QuestionnaireVersion.Status.DRAFT,
        age_form=version.age_form,
        version_number=next_number,
    )

    item_map: dict[int, QuestionItem] = {}
    for item in version.items.all().order_by("sort_order", "id"):
        clone = QuestionItem.objects.create(
            version=new_version,
            code=item.code,
            text=item.text,
            answer_type=item.answer_type,
            choices=item.choices,
            sort_order=item.sort_order,
        )
        item_map[item.pk] = clone

    for cond in ShowCondition.objects.filter(item__version=version).select_related(
        "item", "source_item"
    ):
        ShowCondition.objects.create(
            item=item_map[cond.item_id],
            source_item=item_map[cond.source_item_id],
            operator=cond.operator,
            value=cond.value,
        )

    return new_version
