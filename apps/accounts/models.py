"""Модели пользователей (заготовка этапа 1, без ролей и бизнес-логики)."""
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Пользователь системы. Роли и обязательная смена пароля — на этапе 2."""

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
