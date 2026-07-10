"""Tests for the house-framing formula kinds added on top of per_spacing and
per_stock_length: per_length, per_area_spacing, per_area_coverage, per_count,
header, and fixed_count."""
from decimal import Decimal

from django.test import TestCase

from catalog.models import MaterialLength, MaterialProduct

from .calculations import evaluate_rule, generate_line_items
from .models import Assembly, CalculationRule, LineItem

Kind = CalculationRule.FormulaKind


def make_ft_material(name, lengths=(8, 10, 12, 14, 16, 18, 20, 24), default=16):
    material = MaterialProduct.objects.create(name=name, input_type=MaterialProduct.InputType.FT)
    for length_ft in lengths:
        MaterialLength.objects.create(product=material, length_ft=length_ft, is_default=(length_ft == default))
    return material


class HouseFormulaTests(TestCase):
    def setUp(self):
        self.lumber = make_ft_material('2x10 Test')
        self.sheet = MaterialProduct.objects.create(name='Sheet Test', input_type=MaterialProduct.InputType.EACH)
        self.assembly = Assembly.objects.create(name='Test', tool_type='area')

    def _rule(self, **kwargs):
        defaults = {'assembly': self.assembly, 'material': self.lumber, 'role': 'Test'}
        defaults.update(kwargs)
        return CalculationRule.objects.create(**defaults)

    def test_per_length_cuts_to_smallest_covering_stock(self):
        rule = self._rule(formula_kind=Kind.PER_LENGTH, multiplier=2)
        quantity, length, _ = evaluate_rule(rule, {'length_ft': Decimal('13.2')}, {})
        self.assertEqual(quantity, 2)
        self.assertEqual(length, 14)  # smallest stock covering 13.2 ft

    def test_per_area_spacing_horizontal_members(self):
        # 24 ft wide x 12 ft deep deck, members run horizontally: 24 ft long,
        # spaced up the 12 ft depth at 16" OC -> ceil(144/16)+1 = 10 members.
        rule = self._rule(formula_kind=Kind.PER_AREA_SPACING)
        measurement = {'bbox_width_ft': Decimal('24'), 'bbox_height_ft': Decimal('12')}
        quantity, length, _ = evaluate_rule(rule, measurement, {'spacing_in': 16})
        self.assertEqual(quantity, 10)
        self.assertEqual(length, 24)

    def test_per_area_spacing_vertical_members(self):
        # Same deck, members run vertically: 12 ft long, spaced across 24 ft
        # at 16" OC -> ceil(288/16)+1 = 19 members.
        rule = self._rule(formula_kind=Kind.PER_AREA_SPACING)
        measurement = {'bbox_width_ft': Decimal('24'), 'bbox_height_ft': Decimal('12')}
        quantity, length, _ = evaluate_rule(rule, measurement, {'spacing_in': 16, 'member_direction': 'vertical'})
        self.assertEqual(quantity, 19)
        self.assertEqual(length, 12)

    def test_per_area_coverage_sheets(self):
        # 288 sqft / 32 sqft per sheet = 9 sheets
        rule = self._rule(formula_kind=Kind.PER_AREA_COVERAGE, material=self.sheet, coverage_sqft=Decimal('32'))
        quantity, length, _ = evaluate_rule(rule, {'area_sqft': Decimal('288')}, {})
        self.assertEqual(quantity, 9)
        self.assertIsNone(length)

    def test_per_area_coverage_requires_coverage(self):
        rule = self._rule(formula_kind=Kind.PER_AREA_COVERAGE, material=self.sheet)
        with self.assertRaises(ValueError):
            evaluate_rule(rule, {'area_sqft': Decimal('288')}, {})

    def test_per_count(self):
        rule = self._rule(formula_kind=Kind.PER_COUNT, material=self.sheet, multiplier=2)
        quantity, length, _ = evaluate_rule(rule, {'count': 5}, {})
        self.assertEqual(quantity, 10)
        self.assertIsNone(length)

    def test_header_adds_bearing_and_rounds_to_stock(self):
        # 6 ft opening + 0.25 ft bearing = 6.25 ft -> 8 ft stock, double header
        rule = self._rule(formula_kind=Kind.HEADER, multiplier=2)
        quantity, length, _ = evaluate_rule(rule, {'length_ft': Decimal('6')}, {})
        self.assertEqual(quantity, 2)
        self.assertEqual(length, 8)

    def test_fixed_count(self):
        rule = self._rule(formula_kind=Kind.FIXED_COUNT, multiplier=2)
        quantity, length, _ = evaluate_rule(rule, {'length_ft': Decimal('6')}, {})
        self.assertEqual(quantity, 2)
        self.assertIsNone(length)

    def test_per_spacing_sets_stud_length_from_wall_height(self):
        rule = self._rule(formula_kind=Kind.PER_SPACING, extra=1)
        quantity, length, _ = evaluate_rule(rule, {'length_ft': Decimal('20')}, {'stud_spacing_in': 16, 'wall_height_in': 108})
        self.assertEqual(quantity, 16)
        self.assertEqual(length, 10)  # 108 in = 9 ft -> smallest stock is 10 ft

    def test_per_stock_length_uses_perimeter_for_areas(self):
        # Rim board around a 24x12 deck: 72 ft perimeter / 16 ft default = 5 pieces
        rule = self._rule(formula_kind=Kind.PER_STOCK_LENGTH, multiplier=1)
        quantity, length, _ = evaluate_rule(rule, {'perimeter_ft': Decimal('72')}, {})
        self.assertEqual(quantity, 5)
        self.assertEqual(length, 16)


class SeededHouseAssemblyTests(TestCase):
    """The shipped assemblies produce a sane whole-floor material list."""

    def _estimate(self):
        from accounts.models import Account
        from projects.models import Estimate, Project
        account = Account.objects.create(name='Test Co')
        project = Project.objects.create(account=account, name='House')
        return Estimate.objects.create(project=project)

    def test_floor_joist_assembly_generates_joists_rim_and_subfloor(self):
        estimate = self._estimate()
        assembly = Assembly.objects.get(name='2x10 Floor Joists - 16 in OC', account__isnull=True)
        measurement = {
            'area_sqft': Decimal('288'), 'perimeter_ft': Decimal('72'),
            'bbox_width_ft': Decimal('24'), 'bbox_height_ft': Decimal('12'),
        }
        generate_line_items(estimate, assembly, measurement, {'spacing_in': 16})
        roles = {item.role: item for item in LineItem.objects.filter(estimate=estimate)}
        self.assertIn('Floor Joist', roles)
        self.assertIn('Rim Board', roles)
        self.assertIn('Subfloor', roles)
        # 10 joists * 1.05 waste -> 11; subfloor 9 sheets * 1.10 -> 10
        self.assertEqual(roles['Floor Joist'].quantity, 11)
        self.assertEqual(roles['Subfloor'].quantity, 10)

    def test_opening_assembly_generates_header_and_studs(self):
        estimate = self._estimate()
        assembly = Assembly.objects.get(name='Window/Door Opening - 2x10 Header (2x6 Wall)', account__isnull=True)
        generate_line_items(estimate, assembly, {'length_ft': Decimal('6')}, {'stud_spacing_in': 16})
        roles = {item.role: item for item in LineItem.objects.filter(estimate=estimate)}
        self.assertEqual(roles['Header'].quantity, 2)
        self.assertEqual(roles['Header'].length_ft, 8)
        self.assertEqual(roles['King Stud'].quantity, 2)
        self.assertEqual(roles['Trimmer Stud'].quantity, 2)
        self.assertIn('Cripple Stud', roles)
