"""URL раздела «Сотрудники»."""
from django.urls import path

from apps.directory import views

urlpatterns = [
    path("employees/", views.EmployeeListView.as_view(), name="employee_staff_list"),
    path(
        "employees/new/",
        views.EmployeeCreateView.as_view(),
        name="employee_staff_create",
    ),
    path(
        "employees/<int:pk>/edit/",
        views.EmployeeEditView.as_view(),
        name="employee_staff_edit",
    ),
]
