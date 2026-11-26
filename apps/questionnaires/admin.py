from django.contrib import admin

from .models import QuestionItem, QuestionnaireTemplate, QuestionnaireVersion, ShowCondition


class CanEditQuestionnairesMixin:
    """Шаблонные ModelAdmin доступны только с флагом can_edit_questionnaires."""

    def _allowed(self, request) -> bool:
        user = request.user
        return bool(
            user.is_authenticated
            and user.is_active
            and getattr(user, "can_edit_questionnaires", False)
        )

    def has_module_permission(self, request):
        return self._allowed(request)

    def has_view_permission(self, request, obj=None):
        return self._allowed(request)

    def has_add_permission(self, request):
        return self._allowed(request)

    def has_change_permission(self, request, obj=None):
        return self._allowed(request)

    def has_delete_permission(self, request, obj=None):
        return self._allowed(request)


class QuestionItemInline(admin.TabularInline):
    model = QuestionItem
    extra = 0


@admin.register(QuestionnaireTemplate)
class QuestionnaireTemplateAdmin(CanEditQuestionnairesMixin, admin.ModelAdmin):
    list_display = ("id", "name", "is_demo", "created_at")
    list_filter = ("is_demo",)


@admin.register(QuestionnaireVersion)
class QuestionnaireVersionAdmin(CanEditQuestionnairesMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "template",
        "age_form",
        "version_number",
        "status",
        "published_at",
    )
    list_filter = ("status", "age_form", "template")
    inlines = [QuestionItemInline]


@admin.register(QuestionItem)
class QuestionItemAdmin(CanEditQuestionnairesMixin, admin.ModelAdmin):
    list_display = ("id", "code", "version", "answer_type", "sort_order")
    list_filter = ("answer_type", "version__template")
    search_fields = ("code", "text")


@admin.register(ShowCondition)
class ShowConditionAdmin(CanEditQuestionnairesMixin, admin.ModelAdmin):
    list_display = ("id", "item", "source_item", "operator", "value")
