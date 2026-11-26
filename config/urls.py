"""Корневые URL проекта ДАР-Скрин."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.directory.urls")),
    path("", include("apps.screenings.urls")),
    path("", include("apps.accounts.urls")),
]
