from django.contrib import admin

from .models import QuestionItem, QuestionnaireTemplate, QuestionnaireVersion, ShowCondition


class QuestionItemInline(admin.TabularInline):
    model = QuestionItem
    extra = 0


@admin.register(QuestionnaireTemplate)
class QuestionnaireTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_demo", "created_at")
    list_filter = ("is_demo",)


@admin.register(QuestionnaireVersion)
class QuestionnaireVersionAdmin(admin.ModelAdmin):
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
class QuestionItemAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "version", "answer_type", "sort_order")
    list_filter = ("answer_type", "version__template")
    search_fields = ("code", "text")


@admin.register(ShowCondition)
class ShowConditionAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "source_item", "operator", "value")
