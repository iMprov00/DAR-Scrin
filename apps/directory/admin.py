from django.contrib import admin

from .models import Department, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "organization")
    list_filter = ("organization",)


# EmployeeProfile ведётся в основном интерфейсе «Сотрудники», не в /admin/.
