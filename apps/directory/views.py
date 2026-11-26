"""Раздел «Сотрудники» в основном интерфейсе ДАР-Скрин."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from apps.directory.forms import StaffMemberForm
from apps.directory.models import EmployeeProfile, Organization
from apps.directory.services.staff import save_staff_member

User = get_user_model()


def _require_org_admin(user) -> None:
    if not user.is_authenticated or not user.is_active or not user.is_org_admin:
        raise PermissionDenied("Раздел доступен администратору организации.")


@method_decorator(login_required, name="dispatch")
class EmployeeListView(View):
    def get(self, request):
        _require_org_admin(request.user)
        profiles = (
            EmployeeProfile.objects.select_related("user", "department", "organization")
            .order_by("user__last_name", "user__username")
        )
        return render(
            request,
            "directory/employee_list.html",
            {"profiles": profiles, "layout": "admin"},
        )


@method_decorator(login_required, name="dispatch")
class EmployeeCreateView(View):
    def get(self, request):
        _require_org_admin(request.user)
        org = Organization.objects.order_by("id").first()
        form = StaffMemberForm(organization=org)
        return render(
            request,
            "directory/employee_form.html",
            {"form": form, "title": "Новый сотрудник", "layout": "admin"},
        )

    def post(self, request):
        _require_org_admin(request.user)
        org = Organization.objects.order_by("id").first()
        form = StaffMemberForm(request.POST, organization=org)
        if not form.is_valid():
            return render(
                request,
                "directory/employee_form.html",
                {"form": form, "title": "Новый сотрудник", "layout": "admin"},
                status=400,
            )
        data = form.cleaned_data
        try:
            user, _profile, issued = save_staff_member(
                actor=request.user,
                username=data["username"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                birth_date=data["birth_date"],
                department=data.get("department"),
                is_employee=data["is_employee"],
                is_therapist=data["is_therapist"],
                is_org_admin=data["is_org_admin"],
                is_active=data["is_active"],
                temporary_password=data.get("temporary_password") or None,
            )
        except ValidationError as exc:
            if hasattr(exc, "message_dict"):
                for field, errs in exc.message_dict.items():
                    for err in errs:
                        form.add_error(field if field in form.fields else None, err)
            else:
                form.add_error(None, exc)
            return render(
                request,
                "directory/employee_form.html",
                {"form": form, "title": "Новый сотрудник", "layout": "admin"},
                status=400,
            )
        if issued:
            messages.success(
                request,
                f"Учётка «{user.username}» создана. Временный пароль: {issued}",
            )
        else:
            messages.success(request, f"Учётка «{user.username}» создана.")
        return redirect("employee_staff_list")


@method_decorator(login_required, name="dispatch")
class EmployeeEditView(View):
    def get(self, request, pk: int):
        _require_org_admin(request.user)
        user = get_object_or_404(User, pk=pk)
        org = Organization.objects.order_by("id").first()
        form = StaffMemberForm(organization=org, instance=user)
        return render(
            request,
            "directory/employee_form.html",
            {
                "form": form,
                "title": f"Правка: {user.username}",
                "layout": "admin",
                "edit_user": user,
            },
        )

    def post(self, request, pk: int):
        _require_org_admin(request.user)
        user = get_object_or_404(User, pk=pk)
        org = Organization.objects.order_by("id").first()
        form = StaffMemberForm(request.POST, organization=org, instance=user)
        if not form.is_valid():
            return render(
                request,
                "directory/employee_form.html",
                {
                    "form": form,
                    "title": f"Правка: {user.username}",
                    "layout": "admin",
                    "edit_user": user,
                },
                status=400,
            )
        data = form.cleaned_data
        try:
            user, _profile, issued = save_staff_member(
                actor=request.user,
                username=data["username"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                birth_date=data["birth_date"],
                department=data.get("department"),
                is_employee=data["is_employee"],
                is_therapist=data["is_therapist"],
                is_org_admin=data["is_org_admin"],
                is_active=data["is_active"],
                temporary_password=data.get("temporary_password") or None,
                user=user,
            )
        except ValidationError as exc:
            if hasattr(exc, "message_dict"):
                for field, errs in exc.message_dict.items():
                    for err in errs:
                        form.add_error(field if field in form.fields else None, err)
            else:
                form.add_error(None, exc)
            return render(
                request,
                "directory/employee_form.html",
                {
                    "form": form,
                    "title": f"Правка: {user.username}",
                    "layout": "admin",
                    "edit_user": user,
                },
                status=400,
            )
        if issued:
            messages.success(
                request,
                f"Учётка «{user.username}» обновлена. Новый временный пароль: {issued}",
            )
        else:
            messages.success(request, f"Учётка «{user.username}» обновлена.")
        return redirect("employee_staff_list")
