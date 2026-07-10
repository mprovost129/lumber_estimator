from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import MaterialLength, MaterialProduct

from .forms import CalculationRuleForm, ManualLineItemForm, MaterialForm
from .models import Assembly, CalculationRule

User = get_user_model()


class ManualLineItemFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='forms@example.com', password='testpass123')
        self.account = self.user.account
        self.material = MaterialProduct.objects.create(name='Form Stud', input_type=MaterialProduct.InputType.FT)
        self.other_material = MaterialProduct.objects.create(
            name='Form Other Stud', input_type=MaterialProduct.InputType.FT,
        )
        self.length = MaterialLength.objects.create(product=self.material, length_ft=16, is_default=True)
        self.mismatched_length = MaterialLength.objects.create(
            product=self.other_material, length_ft=12, is_default=True,
        )

    def test_rejects_stock_length_from_a_different_material(self):
        form = ManualLineItemForm(
            data={'material': self.material.id, 'quantity': 3, 'stock_length': self.mismatched_length.id},
            account=self.account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('stock_length', form.errors)

    def test_save_derives_length_ft_from_stock_length(self):
        form = ManualLineItemForm(
            data={'material': self.material.id, 'quantity': 3, 'stock_length': self.length.id},
            account=self.account,
        )
        self.assertTrue(form.is_valid(), form.errors)
        line_item = form.save(commit=False)
        line_item.estimate_id = None  # unsaved-related check not needed for this assertion
        self.assertEqual(line_item.length_ft, Decimal('16'))

    def test_stock_length_optional(self):
        form = ManualLineItemForm(
            data={'material': self.material.id, 'quantity': 3},
            account=self.account,
        )
        self.assertTrue(form.is_valid(), form.errors)
        line_item = form.save(commit=False)
        self.assertIsNone(line_item.length_ft)


class CalculationRuleFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='rule-forms@example.com', password='testpass123')
        self.account = self.user.account
        self.assembly = Assembly.objects.create(name='Form Test Assembly', tool_type='line')
        self.material = MaterialProduct.objects.create(name='Rule Form Stud', input_type=MaterialProduct.InputType.FT)
        self.other_material = MaterialProduct.objects.create(
            name='Rule Form Other Stud', input_type=MaterialProduct.InputType.FT,
        )
        self.length = MaterialLength.objects.create(product=self.material, length_ft=16, is_default=True)
        self.mismatched_length = MaterialLength.objects.create(
            product=self.other_material, length_ft=12, is_default=True,
        )

    def test_rejects_preferred_length_from_a_different_material(self):
        form = CalculationRuleForm(
            data={
                'role': 'Stud', 'material': self.material.id,
                'formula_kind': 'per_spacing', 'multiplier': 1, 'extra': 0,
                'corner_stud_count': 1, 't_intersection_stud_count': 1, 't_backer_stud_count': 1,
                'order': 0, 'preferred_length': self.mismatched_length.id,
            },
            account=self.account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('preferred_length', form.errors)

    def test_accepts_preferred_length_matching_material(self):
        form = CalculationRuleForm(
            data={
                'role': 'Stud', 'material': self.material.id,
                'formula_kind': 'per_spacing', 'multiplier': 1, 'extra': 0,
                'corner_stud_count': 1, 't_intersection_stud_count': 1, 't_backer_stud_count': 1,
                'order': 0, 'preferred_length': self.length.id,
            },
            account=self.account,
        )
        self.assertTrue(form.is_valid(), form.errors)


class MaterialFormLengthUpsertTests(TestCase):
    """MaterialForm.save() upserts MaterialLength rows instead of deleting and
    recreating all of them, so a FK pinned to a specific length (e.g.
    CalculationRule.preferred_length) survives an unrelated or partial edit."""

    def setUp(self):
        self.user = User.objects.create_user(email='material-form@example.com', password='testpass123')
        self.account = self.user.account
        self.material = MaterialProduct.objects.create(
            name='Upsert Test Stud', input_type=MaterialProduct.InputType.FT,
            supported_input_types=[MaterialProduct.InputType.FT],
        )
        self.length_12 = MaterialLength.objects.create(product=self.material, length_ft=12)
        self.length_16 = MaterialLength.objects.create(product=self.material, length_ft=16, is_default=True)
        assembly = Assembly.objects.create(name='Upsert Test Assembly', tool_type='line')
        self.rule = CalculationRule.objects.create(
            assembly=assembly, material=self.material, role='Stud',
            formula_kind=CalculationRule.FormulaKind.PER_SPACING, preferred_length=self.length_16,
        )

    def _form(self, lengths, default_length, instance=None):
        return MaterialForm(
            data={
                'name': self.material.name, 'category': MaterialProduct.Category.STUDS,
                'species': '', 'grade': '', 'nominal_dimension': '',
                'supported_input_types': [MaterialProduct.InputType.FT],
                'input_type': MaterialProduct.InputType.FT,
                'lengths': lengths, 'default_length': default_length,
            },
            instance=instance or self.material,
            account=self.account,
        )

    def test_noop_resave_preserves_length_pks(self):
        form = self._form('12, 16', '16')
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertTrue(MaterialLength.objects.filter(pk=self.length_12.pk).exists())
        self.assertTrue(MaterialLength.objects.filter(pk=self.length_16.pk).exists())
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.preferred_length_id, self.length_16.pk)

    def test_partial_edit_preserves_surviving_length_pk(self):
        # Drop 12 ft, add 20 ft - 16 ft (the pinned length) is untouched.
        form = self._form('16, 20', '16')
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertFalse(MaterialLength.objects.filter(pk=self.length_12.pk).exists())
        self.assertTrue(MaterialLength.objects.filter(pk=self.length_16.pk).exists())
        self.assertTrue(self.material.lengths.filter(length_ft=20).exists())
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.preferred_length_id, self.length_16.pk)

    def test_changing_default_flips_flag_without_new_pk(self):
        form = self._form('12, 16', '12')
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.length_12.refresh_from_db()
        self.length_16.refresh_from_db()
        self.assertTrue(self.length_12.is_default)
        self.assertFalse(self.length_16.is_default)
