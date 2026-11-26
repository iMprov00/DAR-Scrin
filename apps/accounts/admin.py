from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Роли ДАР-Скрин",
            {
                "fields": (
                    "is_employee",
                    "is_therapist",
                    "is_org_admin",
                    "can_edit_questionnaires",
                    "must_change_password",
                ),
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "is_employee",
        "is_therapist",
        "is_org_admin",
        "is_active",
        "is_staff",
    )
    list_filter = (
        "is_employee",
        "is_therapist",
        "is_org_admin",
        "is_active",
        "is_staff",
    )
