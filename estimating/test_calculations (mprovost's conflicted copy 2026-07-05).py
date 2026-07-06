import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.models import Account
from catalog.models import MaterialLength, MaterialProduct
from plans.models import Trace
from plans.test_traces import make_plan_page
from projects.models import Estimate, Project

from .calculations import (
    apply_waste,
    calculate_raw_quantity,
    evaluate_rule,
    generate_line_items,
)
from .models import Assembly, CalculationRule, LineItem

User = get_user_model()


class FormulaTests(TestCase):
    def setUp(self):
        self.material = MaterialProduct.objects.create(name='Test Stud Stock', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=self.material, length_ft=16, is_default=True)

    def _rule(self, **kwargs):
        assembly = Assembly.objects.create(name='Test Assembly', tool_type='line')
        defaults = {'assembly': assembly, 'material': self.material, 'role': 'Test Role'}
        defaults.update(kwargs)
        return CalculationRule.objects.create(**defaults)

    def test_per_spacing_formula(self):
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_SPACING, extra=1)
        # 20 ft wall, 16" OC: ceil(240 / 16) + 1 = 15 + 1 = 16
        self.assertEqual(calculate_raw_quantity(rule, Decimal('20'), {'stud_spacing_in': 16}), 16)

    def test_per_spacing_formula_defaults_to_16_inch_oc_when_missing(self):
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_SPACING, extra=1)
        self.assertEqual(calculate_raw_quantity(rule, Decimal('20'), {}), 16)

    def test_per_stock_length_formula(self):
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_STOCK_LENGTH, multiplier=2)
        # 20 ft wall / 16 ft stock = ceil(1.25) = 2 pieces, x2 multiplier = 4
        self.assertEqual(calculate_raw_quantity(rule, Decimal('20'), {}), 4)

    def test_per_spacing_subtracts_opening_deduction(self):
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_SPACING, extra=1)
        # 20ft wall minus a 4ft opening = 16ft: ceil(192/16)+1 = 12+1 = 13
        measurement = {'length_ft': Decimal('20')}
        raw, _ = evaluate_rule(rule, measurement, {'stud_spacing_in': 16}, opening_deduction_ft=Decimal('4'))
        self.assertEqual(raw, 13)

    def test_per_spacing_deduction_clamps_at_zero(self):
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_SPACING, extra=1)
        # A deduction larger than the wall itself must not go negative.
        measurement = {'length_ft': Decimal('5')}
        raw, _ = evaluate_rule(rule, measurement, {'stud_spacing_in': 16}, opening_deduction_ft=Decimal('20'))
        self.assertEqual(raw, 1)  # just `extra`, since the effective length floors at 0

    def test_per_spacing_adds_corner_studs(self):
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_SPACING, corner_stud_count=2)
        # Base count for a 20ft wall @ 16" OC: ceil(240/16) = 15. Plus 1 corner occurrence x 2 studs.
        junctions = {'corner_count': 1, 'partition_t_count': 0, 'through_t_count': 0}
        raw, _ = evaluate_rule(rule, {'length_ft': Decimal('20')}, {'stud_spacing_in': 16}, junctions=junctions)
        self.assertEqual(raw, 17)

    def test_per_spacing_adds_partition_and_through_t_studs(self):
        rule = self._rule(
            formula_kind=CalculationRule.FormulaKind.PER_SPACING,
            t_intersection_stud_count=1, t_backer_stud_count=3,
        )
        # Base: ceil(240/16) = 15. Plus 1 partition occurrence x 1, plus 2 through occurrences x 3.
        junctions = {'corner_count': 0, 'partition_t_count': 1, 'through_t_count': 2}
        raw, _ = evaluate_rule(rule, {'length_ft': Decimal('20')}, {'stud_spacing_in': 16}, junctions=junctions)
        self.assertEqual(raw, 15 + 1 + 6)

    def test_per_spacing_with_no_junctions_matches_baseline(self):
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_SPACING)
        raw, _ = evaluate_rule(rule, {'length_ft': Decimal('20')}, {'stud_spacing_in': 16})
        self.assertEqual(raw, 15)  # junctions=None defaults to all-zero, unaffected by nonzero defaults on the rule

    def test_per_spacing_piece_length_subtracts_plate_allowance_for_precut_studs(self):
        # 97.125" wall (8'-1-1/8") minus the standard 4.5" plate allowance
        # (double top + single bottom plate) = 92.625" = 7.71875 ft stud -
        # matches plans.framing's elevation preview and the seeded precut length.
        stud = MaterialProduct.objects.create(name='Test Precut Stud', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=stud, length_ft=Decimal('7.71875'))
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_SPACING, material=stud)
        _, piece_length = evaluate_rule(
            rule, {'length_ft': Decimal('20')}, {'stud_spacing_in': 16, 'wall_height_in': 97.125},
        )
        self.assertEqual(piece_length, Decimal('7.71875'))

    def test_per_spacing_piece_length_none_without_wall_height(self):
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_SPACING)
        _, piece_length = evaluate_rule(rule, {'length_ft': Decimal('20')}, {'stud_spacing_in': 16})
        self.assertIsNone(piece_length)

    def test_per_spacing_piece_length_none_when_deduction_would_go_non_positive(self):
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_SPACING)
        _, piece_length = evaluate_rule(
            rule, {'length_ft': Decimal('20')}, {'stud_spacing_in': 16, 'wall_height_in': 4},
        )
        self.assertIsNone(piece_length)

    def test_unknown_formula_kind_raises(self):
        rule = self._rule(formula_kind=CalculationRule.FormulaKind.PER_STOCK_LENGTH)
        rule.formula_kind = 'not_a_real_kind'
        with self.assertRaises(ValueError):
            calculate_raw_quantity(rule, Decimal('20'), {})

    def test_per_box_formula(self):
        nails = MaterialProduct.objects.create(
            name='Test Framing Nails', input_type=MaterialProduct.InputType.BOX, quantity_per_box=2500,
        )
        rule = CalculationRule.objects.create(
            assembly=Assembly.objects.create(name='Test Fastener Assembly', tool_type='line'),
            material=nails, role='Framing Nails', formula_kind=CalculationRule.FormulaKind.PER_BOX,
            units_per_measurement=Decimal('10'),
        )
        # 40ft wall x 10 nails/ft = 400 nails -> ceil(400 / 2500) = 1 box.
        self.assertEqual(calculate_raw_quantity(rule, Decimal('40'), {}), 1)

    def test_per_box_requires_units_per_measurement(self):
        nails = MaterialProduct.objects.create(
            name='Test Framing Nails 2', input_type=MaterialProduct.InputType.BOX, quantity_per_box=2500,
        )
        rule = CalculationRule.objects.create(
            assembly=Assembly.objects.create(name='Test Fastener Assembly 2', tool_type='line'),
            material=nails, role='Framing Nails', formula_kind=CalculationRule.FormulaKind.PER_BOX,
        )
        with self.assertRaises(ValueError):
            calculate_raw_quantity(rule, Decimal('40'), {})


class ApplyWasteTests(TestCase):
    def test_zero_waste_leaves_quantity_unchanged(self):
        self.assertEqual(apply_waste(10, Decimal('0')), 10)

    def test_waste_rounds_up(self):
        # 10 * 1.10 = 11.0 -> 11
        self.assertEqual(apply_waste(10, Decimal('0.10')), 11)
        # 9 * 1.10 = 9.9 -> 10
        self.assertEqual(apply_waste(9, Decimal('0.10')), 10)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GenerateLineItemsTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email='calc@example.com', password='testpass123')
        self.project = Project.objects.create(account=user.account, name='Calc House')
        self.estimate = Estimate.objects.create(project=self.project)

        self.stud = MaterialProduct.objects.create(name='Test 2x6', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=self.stud, length_ft=16, is_default=True)

        self.assembly = Assembly.objects.create(name='Test Wall Assembly', tool_type='line')
        self.stud_rule = CalculationRule.objects.create(
            assembly=self.assembly, material=self.stud, role='Stud',
            formula_kind=CalculationRule.FormulaKind.PER_SPACING, extra=1,
            waste_factor=Decimal('0.10'), order=1,
        )
        self.plate_rule = CalculationRule.objects.create(
            assembly=self.assembly, material=self.stud, role='Top Plate',
            formula_kind=CalculationRule.FormulaKind.PER_STOCK_LENGTH, multiplier=2,
            waste_factor=Decimal('0'), order=2,
        )

    def test_generates_one_line_item_per_rule(self):
        items = generate_line_items(
            self.estimate, self.assembly, Decimal('20'), {'stud_spacing_in': 16},
        )
        self.assertEqual(len(items), 2)

        stud_item = LineItem.objects.get(calculation_rule=self.stud_rule)
        self.assertEqual(stud_item.material, self.stud)
        self.assertEqual(stud_item.role, 'Stud')
        self.assertEqual(stud_item.quantity, 18)  # ceil(16 * 1.10) = 18
        self.assertEqual(stud_item.source, LineItem.Source.TOOL)
        self.assertIsNone(stud_item.length_ft)

        plate_item = LineItem.objects.get(calculation_rule=self.plate_rule)
        self.assertEqual(plate_item.quantity, 4)
        self.assertEqual(plate_item.length_ft, 16)

    def test_regenerating_for_same_trace_replaces_not_duplicates(self):
        page = make_plan_page(self.project)
        trace = Trace.objects.create(
            plan_page=page, tool_type='line', geometry=[{'x': 0, 'y': 0}, {'x': 10, 'y': 0}],
        )

        generate_line_items(self.estimate, self.assembly, Decimal('20'), {'stud_spacing_in': 16}, trace=trace)
        generate_line_items(self.estimate, self.assembly, Decimal('30'), {'stud_spacing_in': 24}, trace=trace)

        self.assertEqual(LineItem.objects.filter(estimate=self.estimate, trace=trace).count(), 2)

    def test_regenerating_never_touches_manual_line_items(self):
        manual_item = LineItem.objects.create(
            estimate=self.estimate, material=self.stud, role='Manual Add', quantity=5,
            source=LineItem.Source.MANUAL,
        )

        generate_line_items(self.estimate, self.assembly, Decimal('20'), {'stud_spacing_in': 16})

        manual_item.refresh_from_db()
        self.assertEqual(manual_item.quantity, 5)
        self.assertEqual(manual_item.source, LineItem.Source.MANUAL)


class AssemblyVisibilityTests(TestCase):
    def test_visible_to_includes_global_and_own_account_only(self):
        account_a = Account.objects.create(name='A')
        account_b = Account.objects.create(name='B')
        global_assembly = Assembly.objects.create(name='Global Wall', tool_type='line')
        assembly_a = Assembly.objects.create(account=account_a, name='A Custom Wall', tool_type='line')
        assembly_b = Assembly.objects.create(account=account_b, name='B Custom Wall', tool_type='line')

        visible = Assembly.objects.visible_to(account_a)
        self.assertIn(global_assembly, visible)
        self.assertIn(assembly_a, visible)
        self.assertNotIn(assembly_b, visible)


class SeededAssemblyMatchesReferenceSpecTests(TestCase):
    """Regression tests against House_Lumber_Takeoff_Formulas.xlsx's worked
    examples, run against the actual migrated seed data (not a fresh fixture)
    so a future migration can't silently reintroduce the rafter-multiplier bug
    this file fixes."""

    def test_rafters_double_for_both_roof_planes(self):
        rule = CalculationRule.objects.get(assembly__name='2x8 Roof Rafters - 16 in OC', role='Rafter')
        # Spreadsheet's Roof Takeoff example: 40ft building, 24in OC, 2 planes, 10% waste -> 47.
        measurement = {'bbox_width_ft': Decimal('40'), 'bbox_height_ft': Decimal('16')}
        raw, _ = evaluate_rule(rule, measurement, {'spacing_in': 24, 'member_direction': 'vertical'})
        self.assertEqual(apply_waste(raw, rule.waste_factor), 47)

    def test_seeded_wall_assembly_includes_framing_nails_per_box(self):
        rule = CalculationRule.objects.get(assembly__name='2x6 Wall - 16 in OC', role='Framing Nails')
        self.assertEqual(rule.formula_kind, CalculationRule.FormulaKind.PER_BOX)
        # 40ft wall x 10 nails/ft = 400 nails -> ceil(400 / 2500) = 1 box.
        raw, _ = evaluate_rule(rule, {'length_ft': Decimal('40')}, {})
        self.assertEqual(raw, 1)
