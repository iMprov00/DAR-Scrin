"""URL интерфейса сотрудника и терапевта (этап 3)."""
from django.urls import path

from apps.screenings import views

urlpatterns = [
    path(
        "my/assignments/",
        views.EmployeeAssignmentListView.as_view(),
        name="employee_assignment_list",
    ),
    path(
        "my/assignments/<int:pk>/",
        views.EmployeeAssignmentDetailView.as_view(),
        name="employee_assignment_detail",
    ),
    path(
        "my/assignments/<int:pk>/autosave/",
        views.EmployeeAssignmentAutosaveView.as_view(),
        name="employee_assignment_autosave",
    ),
    path(
        "my/assignments/<int:pk>/submit/",
        views.EmployeeAssignmentSubmitView.as_view(),
        name="employee_assignment_submit",
    ),
    path(
        "therapist/assignments/",
        views.TherapistAssignmentListView.as_view(),
        name="therapist_assignment_list",
    ),
    path(
        "therapist/assignments/<int:pk>/",
        views.TherapistAssignmentDetailView.as_view(),
        name="therapist_assignment_detail",
    ),
    path(
        "therapist/assign/",
        views.TherapistAssignView.as_view(),
        name="therapist_assign",
    ),
    path(
        "therapist/assignments/<int:pk>/return/",
        views.TherapistReturnView.as_view(),
        name="therapist_return",
    ),
    path(
        "therapist/assignments/<int:pk>/review/",
        views.TherapistReviewView.as_view(),
        name="therapist_review",
    ),
    path(
        "therapist/assignments/<int:pk>/due-date/",
        views.TherapistChangeDueDateView.as_view(),
        name="therapist_change_due_date",
    ),
    path(
        "therapist/assignments/<int:pk>/cancel/",
        views.TherapistCancelView.as_view(),
        name="therapist_cancel",
    ),
]
