"""T01 — граница возраста 64 / 65."""
from datetime import date

from django.test import TestCase

from apps.directory.services.age import AgeForm, full_years_on, select_age_form


class AgeFormBoundaryTests(TestCase):
    """T01: до дня 65-летия — under_65; в день 65 и позже — age_65_plus."""

    def test_t01_day_before_65th_birthday(self):
        birth = date(1960, 3, 15)
        on_date = date(2025, 3, 14)
        self.assertEqual(full_years_on(birth, on_date), 64)
        self.assertEqual(select_age_form(birth, on_date), AgeForm.UNDER_65)

    def test_t01_on_65th_birthday(self):
        birth = date(1960, 3, 15)
        on_date = date(2025, 3, 15)
        self.assertEqual(full_years_on(birth, on_date), 65)
        self.assertEqual(select_age_form(birth, on_date), AgeForm.AGE_65_PLUS)

    def test_t01_after_65th_birthday(self):
        birth = date(1960, 3, 15)
        on_date = date(2025, 3, 16)
        self.assertEqual(select_age_form(birth, on_date), AgeForm.AGE_65_PLUS)
