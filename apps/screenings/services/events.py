"""
Простой программный интерфейс событий без брокера/очереди/outbox
(docs/architecture.md): assigned, submitted, returned, reviewed.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

Listener = Callable[..., Any]

_LISTENERS: dict[str, list[Listener]] = defaultdict(list)


def on(event_name: str, listener: Listener) -> None:
    _LISTENERS[event_name].append(listener)


def emit(event_name: str, **payload: Any) -> None:
    for listener in list(_LISTENERS.get(event_name, [])):
        listener(**payload)


def reset_listeners() -> None:
    """Для тестов: очистить подписки."""
    _LISTENERS.clear()
