"""Сервисы учёток: деактивация и смена пароля (допущение)."""
from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.accounts.models import User


def deactivate_user(user: User) -> User:
    """Отключает вход и сбрасывает сессии; история обследований не удаляется."""
    user.is_active = False
    user.save(update_fields=["is_active"])

    # Сброс сессий по session_key, где в данных есть этот user_id.
    now = timezone.now()
    for session in Session.objects.filter(expire_date__gte=now):
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) == str(user.pk):
            session.delete()
    return user


def user_must_change_password(user: User) -> bool:
    """Допущение docs/decisions.md п.1 — без UI на этапе 2."""
    return bool(user.must_change_password)
