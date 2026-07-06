from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Account
from catalog.models import MaterialProduct

from .calculations import evaluate_rule
from .models import Assembly, CalculationRule, Formula

User = get_user_model()


class FormulaEvaluationTests(TestCase):
    def test_formula_can_build_on_stock_measurement(self):
        stock = Formula.objects.get(name='Line LF', account__isnull=True)
        formula = Formula.objects.create(
            account=Account.objects.create(name='Builder'),
            name='Triple line',
            measurement_kind=Formula.MeasurementKind.LINE_LF,
            base_formula=stock,
            multiplier=Decimal('3'),
        )
        material = MaterialProduct.objects.create(name='Formula material')
        assembly = Assembly.objects.create(account=formula.account, name='Formula assembly', tool_type='line')
        rule = CalculationRule.objects.create(
            assembly=assembly,
            material=material,
            role='Three runs',
            formula=formula,
        )

        quantity, length = evaluate_rule(rule, {'length_ft': Decimal('12.5')}, {})

        self.assertEqual(quantity, 38)
        self.assertIsNone(length)
        self.assertEqual(formula.expression, 'Line LF × 3')


class FormulaLibraryViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='library@example.com', password='testpass123')
        self.client.force_login(self.user)

    def test_library_shows_stock_formulas(self):
        response = self.client.get(reverse('estimating:library'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Line LF')
        self.assertContains(response, 'Area SF')

    def test_user_can_create_derived_formula(self):
        stock = Formula.objects.get(name='Line LF', account__isnull=True)

        response = self.client.post(reverse('estimating:formula-create'), {
            'name': 'Three plate runs',
            'measurement_kind': Formula.MeasurementKind.LINE_LF,
            'base_formula': stock.pk,
            'multiplier': '3',
            'addend': '0',
            'description': 'Bottom plate and double top plate.',
        })

        self.assertRedirects(response, reverse('estimating:library'))
        formula = Formula.objects.get(name='Three plate runs')
        self.assertEqual(formula.account, self.user.account)
        self.assertEqual(formula.multiplier, Decimal('3'))

    def test_user_cannot_build_from_another_accounts_formula(self):
        other_account = Account.objects.create(name='Other')
        private = Formula.objects.create(
            account=other_account,
            name='Private formula',
            measurement_kind=Formula.MeasurementKind.LINE_LF,
        )

        response = self.client.post(reverse('estimating:formula-create'), {
            'name': 'Unauthorized derivative',
            'measurement_kind': Formula.MeasurementKind.LINE_LF,
            'base_formula': private.pk,
            'multiplier': '2',
            'addend': '0',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Formula.objects.filter(name='Unauthorized derivative').exists())

    def test_user_can_create_assembly_with_library_formula(self):
        material = MaterialProduct.objects.create(name='Assembly material')
        formula = Formula.objects.get(name='Line LF', account__isnull=True)

        response = self.client.post(reverse('estimating:assembly-create'), {
            'name': 'Three line runs',
            'tool_type': 'line',
            'description': '',
            'rules-TOTAL_FORMS': '1',
            'rules-INITIAL_FORMS': '0',
            'rules-MIN_NUM_FORMS': '1',
            'rules-MAX_NUM_FORMS': '1000',
            'rules-0-role': 'Line material',
            'rules-0-material': material.pk,
            'rules-0-formula': formula.pk,
            'rules-0-formula_kind': '',
            'rules-0-multiplier': '1',
            'rules-0-extra': '0',
            'rules-0-coverage_sqft': '',
            'rules-0-waste_factor': '0.10',
            'rules-0-order': '1',
            'rules-0-corner_stud_count': '1',
            'rules-0-t_intersection_stud_count': '1',
            'rules-0-t_backer_stud_count': '1',
        })

        self.assertRedirects(response, reverse('estimating:library'))
        assembly = Assembly.objects.get(name='Three line runs')
        self.assertEqual(assembly.account, self.user.account)
        self.assertEqual(assembly.rules.get().formula, formula)

    def test_assembly_creation_rejects_both_formula_and_formula_kind(self):
        # Server-side backstop for CalculationRule.clean()'s XOR rule - the
        # form JS enforces this live, but a request without JS (or a bug in
        # it) must still be rejected rather than silently saving an ambiguous rule.
        material = MaterialProduct.objects.create(name='Ambiguous rule material')
        formula = Formula.objects.get(name='Line LF', account__isnull=True)

        response = self.client.post(reverse('estimating:assembly-create'), {
            'name': 'Ambiguous assembly',
            'tool_type': 'line',
            'description': '',
            'rules-TOTAL_FORMS': '1',
            'rules-INITIAL_FORMS': '0',
            'rules-MIN_NUM_FORMS': '1',
            'rules-MAX_NUM_FORMS': '1000',
            'rules-0-role': 'Sill Plate',
            'rules-0-material': material.pk,
            'rules-0-formula': formula.pk,
            'rules-0-formula_kind': CalculationRule.FormulaKind.PER_STOCK_LENGTH,
            'rules-0-multiplier': '1',
            'rules-0-extra': '0',
            'rules-0-coverage_sqft': '',
            'rules-0-waste_factor': '0',
            'rules-0-order': '1',
            'rules-0-corner_stud_count': '1',
            'rules-0-t_intersection_stud_count': '1',
            'rules-0-t_backer_stud_count': '1',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose either a library formula or a framing formula kind.')
        self.assertFalse(Assembly.objects.filter(name='Ambiguous assembly').exists())

    def test_user_can_create_per_box_rule_with_units_per_measurement(self):
        material = MaterialProduct.objects.create(
            name='Framing Nails Test', input_type=MaterialProduct.InputType.BOX, quantity_per_box=2500,
        )

        response = self.client.post(reverse('estimating:assembly-create'), {
            'name': 'Nail Assembly',
            'tool_type': 'line',
            'description': '',
            'rules-TOTAL_FORMS': '1',
            'rules-INITIAL_FORMS': '0',
            'rules-MIN_NUM_FORMS': '1',
            'rules-MAX_NUM_FORMS': '1000',
            'rules-0-role': 'Framing Nails',
            'rules-0-material': material.pk,
            'rules-0-formula': '',
            'rules-0-formula_kind': CalculationRule.FormulaKind.PER_BOX,
            'rules-0-multiplier': '1',
            'rules-0-extra': '0',
            'rules-0-coverage_sqft': '',
            'rules-0-units_per_measurement': '10',
            'rules-0-waste_factor': '0',
            'rules-0-order': '1',
            'rules-0-corner_stud_count': '1',
            'rules-0-t_intersection_stud_count': '1',
            'rules-0-t_backer_stud_count': '1',
        })

        self.assertRedirects(response, reverse('estimating:library'))
        rule = Assembly.objects.get(name='Nail Assembly').rules.get()
        self.assertEqual(rule.units_per_measurement, Decimal('10'))
