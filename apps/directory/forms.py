"""Формы раздела «Сотрудники» (без групп и permissions Django)."""
from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from apps.directory.models import Department, EmployeeProfile

User = get_user_model()


class StaffMemberForm(forms.Form):
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    username = forms.CharField(label="Логин", max_length=150)
    birth_date = forms.DateField(
        label="Дата рождения",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    department = forms.ModelChoiceField(
        label="Подразделение",
        queryset=Department.objects.none(),
        required=False,
        empty_label="— не указано —",
    )
    is_employee = forms.BooleanField(label="Сотрудник", required=False)
    is_therapist = forms.BooleanField(label="Терапевт", required=False)
    is_org_admin = forms.BooleanField(label="Администратор", required=False)
    is_active = forms.BooleanField(label="Активен", required=False, initial=True)
    temporary_password = forms.CharField(
        label="Временный пароль",
        max_length=128,
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="При создании можно оставить пустым — пароль сгенерируется. "
        "При правке заполняйте, только если нужно выдать новый.",
    )

    def __init__(self, *args, organization=None, instance: User | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        org = organization
        if org is None and instance is not None:
            profile = getattr(instance, "employee_profile", None)
            if profile is not None:
                org = profile.organization
        qs = Department.objects.all().order_by("name")
        if org is not None:
            qs = qs.filter(organization=org)
        self.fields["department"].queryset = qs

        if instance is not None:
            self.fields["username"].initial = instance.username
            self.fields["first_name"].initial = instance.first_name
            self.fields["last_name"].initial = instance.last_name
            self.fields["is_employee"].initial = instance.is_employee
            self.fields["is_therapist"].initial = instance.is_therapist
            self.fields["is_org_admin"].initial = instance.is_org_admin
            self.fields["is_active"].initial = instance.is_active
            profile = EmployeeProfile.objects.filter(user=instance).select_related(
                "department"
            ).first()
            if profile is not None:
                self.fields["birth_date"].initial = profile.birth_date
                self.fields["department"].initial = profile.department_id
        else:
            self.fields["temporary_password"].help_text = (
                "Можно оставить пустым — будет сгенерирован временный пароль."
            )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if " " in username:
            raise forms.ValidationError(
                "Логин без пробелов. ФИО укажите в полях фамилии и имени."
            )
        qs = User.objects.filter(username=username)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Такой логин уже занят.")
        return username

    def clean(self):
        cleaned = super().clean()
        if not (
            cleaned.get("is_employee")
            or cleaned.get("is_therapist")
            or cleaned.get("is_org_admin")
        ):
            raise forms.ValidationError("Выберите хотя бы одну роль.")
        return cleaned
