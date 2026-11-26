from django.contrib import admin

from .models import ActionAudit, AnswerSnapshot, Assignment, DueDateAudit, Screening


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    show_change_link = True
    fields = ("id", "status", "due_date", "age_form", "template_version")
    readonly_fields = fields


@admin.register(Screening)
class ScreeningAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "organization", "created_at")
    inlines = [AssignmentInline]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "screening",
        "status",
        "due_date",
        "age_form",
        "template_version",
    )
    list_filter = ("status", "age_form")
    readonly_fields = ("draft_answers", "draft_revision", "return_comment", "review_comment")


@admin.register(AnswerSnapshot)
class AnswerSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "assignment", "sequence", "created_at")
    readonly_fields = ("assignment", "answers", "sequence", "created_at")

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DueDateAudit)
class DueDateAuditAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "assignment",
        "old_due_date",
        "new_due_date",
        "changed_by",
        "changed_at",
        "reason",
    )
    readonly_fields = (
        "assignment",
        "old_due_date",
        "new_due_date",
        "changed_by",
        "changed_at",
        "reason",
    )


@admin.register(ActionAudit)
class ActionAuditAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "assignment", "actor", "created_at")
    readonly_fields = ("assignment", "actor", "action", "details", "created_at")
