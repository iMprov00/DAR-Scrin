"""Проверка ответов перед отправкой (слой UI; смысл сервисов не меняет)."""
from __future__ import annotations

from typing import Any

from apps.questionnaires.models import QuestionItem, QuestionnaireVersion
from apps.questionnaires.services.visibility import visible_items


def is_answer_present(value: Any) -> bool:
    """Пустой ответ ≠ «нет»: отсутствует ключ / None / '' — нет ответа; False — есть."""
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    return True


def missing_visible_codes(
    version: QuestionnaireVersion, answers: dict[str, Any]
) -> list[str]:
    """Коды видимых пунктов без ответа."""
    missing: list[str] = []
    for item in visible_items(version, answers):
        if not is_answer_present(answers.get(item.code)):
            missing.append(item.code)
    return missing


def parse_answer_value(item: QuestionItem, raw: Any) -> Any:
    """Приведение значения поля формы к типу пункта."""
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip() == "":
        return None

    if item.answer_type == QuestionItem.AnswerType.YES_NO:
        if isinstance(raw, bool):
            return raw
        s = str(raw).strip().lower()
        if s in ("true", "1", "yes", "да"):
            return True
        if s in ("false", "0", "no", "нет"):
            return False
        return None

    if item.answer_type == QuestionItem.AnswerType.NUMBER:
        try:
            text = str(raw).strip().replace(",", ".")
            if "." in text:
                return float(text)
            return int(text)
        except (TypeError, ValueError):
            return None

    if item.answer_type == QuestionItem.AnswerType.SINGLE_CHOICE:
        return str(raw)

    if item.answer_type == QuestionItem.AnswerType.TEXT:
        return str(raw)

    return raw


def answers_from_post(version: QuestionnaireVersion, post) -> dict[str, Any]:
    """Собрать dict ответов из QueryDict / POST по кодам пунктов."""
    items = version.items.all()
    result: dict[str, Any] = {}
    for item in items:
        key = f"answer_{item.code}"
        if key not in post:
            # Альтернативный ключ без префикса (удобно для тестов).
            if item.code not in post:
                continue
            raw = post.get(item.code)
        else:
            raw = post.get(key)
        parsed = parse_answer_value(item, raw)
        if parsed is not None:
            result[item.code] = parsed
    return result
