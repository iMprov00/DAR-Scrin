"""
Пользователи и группы Django не регистрируются в /admin/.
Повседневная работа с учётками — раздел «Сотрудники» в основном UI.
"""
from django.contrib import admin
from django.contrib.auth.models import Group

# Скрыть стандартные группы Django из админки.
try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass
