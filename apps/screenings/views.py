"""
Views этапа 3: сотрудник и терапевт.
Бизнес-логика — только через apps.screenings.services.
"""
from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from apps.directory.models import EmployeeProfile
from apps.questionnaires.services.visibility import is_item_visible
from apps.screenings.forms_validation import (
    answers_from_post,
    missing_visible_codes,
)
from apps.screenings.models import Assignment
from apps.screenings.services import (
    DomainError,
    assign_questionnaire,
    autosave_draft,
    cancel_assignment,
    can_fill_assignment,
    can_manage_assignment,
    can_view_answers,
    can_view_assignment,
    change_due_date,
    get_answers_for_user,
    is_overdue,
    mark_reviewed,
    return_for_revision,
    submit_assignment,
)
from apps.screenings.services.assignments import (
    DUE_DATE_CHANGE_STATUSES,
    EDITABLE_STATUSES,
)


def _get_assignment(pk: int) -> Assignment:
    return get_object_or_404(
        Assignment.objects.select_related(
            "screening",
            "screening__employee",
            "screening__employee__user",
            "screening__employee__department",
            "template_version",
            "template_version__template",
        ),
        pk=pk,
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _domain_message(exc: DomainError) -> str:
    if hasattr(exc, "messages") and exc.messages:
        return "; ".join(str(m) for m in exc.messages)
    return str(exc)


def _questionnaire_context(assignment: Assignment, answers: dict) -> dict:
    version = assignment.template_version
    items = list(
        version.items.prefetch_related("show_conditions__source_item").order_by(
            "sort_order", "id"
        )
    )
    item_rows = []
    for item in items:
        conditions = [
            {
                "source": c.source_item.code,
                "operator": c.operator,
                "value": c.value,
            }
            for c in item.show_conditions.all()
        ]
        item_rows.append(
            {
                "item": item,
                "visible": is_item_visible(item, answers),
                "value": answers.get(item.code),
                "conditions": conditions,
            }
        )
    return {
        "items": items,
        "item_rows": item_rows,
        "is_demo": version.template.is_demo,
        "template_name": version.template.name,
        "editable": assignment.status in EDITABLE_STATUSES,
        "overdue": is_overdue(assignment),
    }


@method_decorator(login_required, name="dispatch")
class EmployeeAssignmentListView(View):
    def get(self, request):
        if not request.user.is_employee:
            return HttpResponseForbidden("Доступ только для сотрудника.")
        qs = (
            Assignment.objects.filter(screening__employee__user=request.user)
            .select_related(
                "template_version__template",
                "screening__employee",
            )
            .order_by("-assigned_at")
        )
        rows = [
            {
                "assignment": a,
                "overdue": is_overdue(a),
                "status_label": a.get_status_display(),
            }
            for a in qs
        ]
        return render(
            request,
            "employee/assignment_list.html",
            {"rows": rows, "layout": "employee"},
        )


@method_decorator(login_required, name="dispatch")
class EmployeeAssignmentDetailView(View):
    def get(self, request, pk: int):
        assignment = _get_assignment(pk)
        if not can_view_assignment(request.user, assignment):
            raise PermissionDenied("Нет доступа к назначению.")
        # Ответы — только через can_view_answers (админ по прямой URL получает 403).
        if not can_view_answers(request.user, assignment):
            raise PermissionDenied("Нет доступа к ответам анкеты.")
        answers = get_answers_for_user(request.user, assignment)
        ctx = {
            "assignment": assignment,
            "answers": answers,
            "can_fill": can_fill_assignment(request.user, assignment)
            and assignment.status in EDITABLE_STATUSES,
            "layout": "employee",
            **_questionnaire_context(assignment, answers),
        }
        return render(request, "employee/assignment_detail.html", ctx)


@method_decorator(login_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class EmployeeAssignmentAutosaveView(View):
    def post(self, request, pk: int):
        assignment = _get_assignment(pk)
        if not can_fill_assignment(request.user, assignment):
            return HttpResponseForbidden("Нет права заполнять это назначение.")
        answers = answers_from_post(assignment.template_version, request.POST)
        expected = request.POST.get("expected_revision")
        expected_revision = int(expected) if expected not in (None, "") else None
        try:
            updated = autosave_draft(
                assignment=assignment,
                actor=request.user,
                answers=answers,
                expected_revision=expected_revision,
            )
        except PermissionDenied:
            return HttpResponseForbidden("Нет права сохранять черновик.")
        except DomainError as exc:
            return HttpResponse(
                f'<span class="autosave-status autosave-error">{_domain_message(exc)}</span>',
                status=409,
            )
        return HttpResponse(
            f'<span class="autosave-status autosave-ok" '
            f'data-revision="{updated.draft_revision}">'
            f"Сохранено · рев. {updated.draft_revision}</span>"
        )


@method_decorator(login_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class EmployeeAssignmentSubmitView(View):
    def post(self, request, pk: int):
        assignment = _get_assignment(pk)
        if not can_fill_assignment(request.user, assignment):
            raise PermissionDenied("Нет права отправлять это назначение.")
        answers = answers_from_post(assignment.template_version, request.POST)
        # Слить с черновиком для проверки видимости.
        merged = dict(assignment.draft_answers or {})
        merged.update(answers)
        missing = missing_visible_codes(assignment.template_version, merged)
        if missing:
            messages.error(
                request,
                "Заполните все видимые пункты перед отправкой: "
                + ", ".join(missing),
            )
            return redirect("employee_assignment_detail", pk=pk)

        expected = request.POST.get("expected_revision")
        expected_revision = int(expected) if expected not in (None, "") else None
        try:
            submit_assignment(
                assignment=assignment,
                actor=request.user,
                answers=answers,
                expected_revision=expected_revision,
            )
        except PermissionDenied:
            raise
        except DomainError as exc:
            messages.error(request, _domain_message(exc))
            return redirect("employee_assignment_detail", pk=pk)

        messages.success(request, "Анкета отправлена.")
        return redirect("employee_assignment_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
class TherapistAssignmentListView(View):
    def get(self, request):
        if not request.user.is_therapist:
            return HttpResponseForbidden("Доступ только для терапевта.")
        qs = Assignment.objects.select_related(
            "screening__employee__user",
            "screening__employee__department",
            "template_version__template",
        ).order_by("-assigned_at")

        status = request.GET.get("status") or ""
        if status:
            qs = qs.filter(status=status)

        overdue_only = request.GET.get("overdue") == "1"
        rows = []
        for a in qs:
            overdue = is_overdue(a)
            if overdue_only and not overdue:
                continue
            rows.append(
                {
                    "assignment": a,
                    "overdue": overdue,
                    "employee": a.screening.employee,
                    "status_label": a.get_status_display(),
                }
            )
        employees = (
            EmployeeProfile.objects.select_related("user", "department")
            .order_by("user__username")
        )
        return render(
            request,
            "therapist/assignment_list.html",
            {
                "rows": rows,
                "status_choices": Assignment.Status.choices,
                "filter_status": status,
                "filter_overdue": overdue_only,
                "employees": employees,
                "layout": "therapist",
            },
        )


@method_decorator(login_required, name="dispatch")
class TherapistAssignmentDetailView(View):
    def get(self, request, pk: int):
        if not request.user.is_therapist:
            return HttpResponseForbidden("Доступ только для терапевта.")
        assignment = _get_assignment(pk)
        if not can_view_assignment(request.user, assignment):
            raise PermissionDenied("Нет доступа к назначению.")
        answers = {}
        if can_view_answers(request.user, assignment):
            answers = get_answers_for_user(request.user, assignment)
        else:
            raise PermissionDenied("Нет доступа к ответам анкеты.")

        ctx = {
            "assignment": assignment,
            "answers": answers,
            "can_manage": can_manage_assignment(request.user, assignment),
            "can_return": assignment.status == Assignment.Status.SUBMITTED,
            "can_review": assignment.status == Assignment.Status.SUBMITTED,
            "can_change_due": assignment.status in DUE_DATE_CHANGE_STATUSES,
            "can_cancel": assignment.status
            not in (Assignment.Status.REVIEWED, Assignment.Status.CANCELED),
            "layout": "therapist",
            **_questionnaire_context(assignment, answers),
        }
        return render(request, "therapist/assignment_detail.html", ctx)


@method_decorator(login_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class TherapistAssignView(View):
    def post(self, request):
        if not request.user.is_therapist:
            return HttpResponseForbidden("Назначать анкету может только терапевт.")
        employee_id = request.POST.get("employee_id")
        due = _parse_date(request.POST.get("due_date"))
        if not employee_id or due is None:
            messages.error(request, "Укажите сотрудника и срок.")
            return redirect("therapist_assignment_list")
        employee = get_object_or_404(EmployeeProfile, pk=employee_id)
        try:
            assignment = assign_questionnaire(
                employee=employee,
                due_date=due,
                actor=request.user,
            )
        except PermissionDenied:
            raise
        except DomainError as exc:
            messages.error(request, _domain_message(exc))
            return redirect("therapist_assignment_list")
        messages.success(request, f"Анкету назначено (№{assignment.pk}).")
        return redirect("therapist_assignment_detail", pk=assignment.pk)


@method_decorator(login_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class TherapistReturnView(View):
    def post(self, request, pk: int):
        assignment = _get_assignment(pk)
        if not can_manage_assignment(request.user, assignment):
            raise PermissionDenied("Возврат доступен только терапевту.")
        comment = (request.POST.get("comment") or "").strip()
        new_due = _parse_date(request.POST.get("new_due_date"))
        if not comment:
            messages.error(request, "Комментарий врача при возврате обязателен.")
            return redirect("therapist_assignment_detail", pk=pk)
        if new_due is None:
            messages.error(
                request,
                "Укажите новый срок (допущение: обязателен, может совпасть с прежним).",
            )
            return redirect("therapist_assignment_detail", pk=pk)
        try:
            return_for_revision(
                assignment=assignment,
                actor=request.user,
                comment=comment,
                new_due_date=new_due,
            )
        except DomainError as exc:
            messages.error(request, _domain_message(exc))
            return redirect("therapist_assignment_detail", pk=pk)
        messages.success(request, "Анкета возвращена на исправление.")
        return redirect("therapist_assignment_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class TherapistReviewView(View):
    def post(self, request, pk: int):
        assignment = _get_assignment(pk)
        if not can_manage_assignment(request.user, assignment):
            raise PermissionDenied("Проверка доступна только терапевту.")
        comment = (request.POST.get("comment") or "").strip()
        try:
            mark_reviewed(
                assignment=assignment,
                actor=request.user,
                comment=comment,
            )
        except DomainError as exc:
            messages.error(request, _domain_message(exc))
            return redirect("therapist_assignment_detail", pk=pk)
        messages.success(request, "Отмечено: проверено.")
        return redirect("therapist_assignment_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class TherapistChangeDueDateView(View):
    def post(self, request, pk: int):
        assignment = _get_assignment(pk)
        if not can_manage_assignment(request.user, assignment):
            raise PermissionDenied("Смена срока доступна только терапевту.")
        new_due = _parse_date(request.POST.get("new_due_date"))
        if new_due is None:
            messages.error(request, "Укажите новый срок.")
            return redirect("therapist_assignment_detail", pk=pk)
        try:
            change_due_date(
                assignment=assignment,
                actor=request.user,
                new_due_date=new_due,
            )
        except DomainError as exc:
            messages.error(request, _domain_message(exc))
            return redirect("therapist_assignment_detail", pk=pk)
        messages.success(request, "Срок изменён.")
        return redirect("therapist_assignment_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class TherapistCancelView(View):
    def post(self, request, pk: int):
        assignment = _get_assignment(pk)
        if not can_manage_assignment(request.user, assignment):
            raise PermissionDenied("Отмена доступна только терапевту.")
        try:
            cancel_assignment(assignment=assignment, actor=request.user)
        except DomainError as exc:
            messages.error(request, _domain_message(exc))
            return redirect("therapist_assignment_detail", pk=pk)
        messages.success(
            request,
            "Назначение отменено (допущение docs/decisions.md).",
        )
        return redirect("therapist_assignment_detail", pk=pk)
