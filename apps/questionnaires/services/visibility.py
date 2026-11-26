"""Условия показа пунктов и фильтрация скрытых ответов для проверки/снимка."""
from __future__ import annotations

from typing import Any

from apps.questionnaires.models import QuestionItem, QuestionnaireVersion, ShowCondition


def _condition_matches(condition: ShowCondition, answers: dict[str, Any]) -> bool:
    source_code = condition.source_item.code
    if source_code not in answers:
        return False
    actual = answers[source_code]
    if condition.operator == ShowCondition.Operator.EQ:
        return actual == condition.value
    return False


def is_item_visible(item: QuestionItem, answers: dict[str, Any]) -> bool:
    """Пункт без условий всегда видима; иначе все условия должны выполняться."""
    conditions = list(item.show_conditions.select_related("source_item"))
    if not conditions:
        return True
    return all(_condition_matches(c, answers) for c in conditions)


def visible_items(
    version: QuestionnaireVersion, answers: dict[str, Any]
) -> list[QuestionItem]:
    items = list(
        version.items.prefetch_related("show_conditions__source_item").order_by(
            "sort_order", "id"
        )
    )
    return [item for item in items if is_item_visible(item, answers)]


def filter_visible_answers(
    version: QuestionnaireVersion, answers: dict[str, Any]
) -> dict[str, Any]:
    """
    Скрытые по условиям ответы не входят в текущую проверку и новый снимок
    (docs/workflow.md). Значения в черновике не стираются этой функцией.
    """
    visible_codes = {item.code for item in visible_items(version, answers)}
    return {code: value for code, value in answers.items() if code in visible_codes}
