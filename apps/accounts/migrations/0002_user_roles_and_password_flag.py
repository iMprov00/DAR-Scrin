from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="can_edit_questionnaires",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Отдельное полномочие на шаблоны в Django Admin; "
                    "не выдаётся всем org_admin автоматически."
                ),
                verbose_name="правка шаблонов анкет",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="is_employee",
            field=models.BooleanField(
                default=False,
                help_text="Роль сотрудника: свои назначения и ответы.",
                verbose_name="сотрудник",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="is_org_admin",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Администратор учёток и подразделений. "
                    "По умолчанию без доступа к ответам анкет."
                ),
                verbose_name="администратор организации",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="is_therapist",
            field=models.BooleanField(
                default=False,
                help_text="Роль терапевта: назначения и проверка по организации.",
                verbose_name="терапевт",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="must_change_password",
            field=models.BooleanField(
                default=False,
                verbose_name="обязательна смена пароля",
            ),
        ),
    ]
