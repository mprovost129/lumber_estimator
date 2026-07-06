import csv
import importlib
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Account
from billing.models import EstimateAccessGrant
from catalog.models import MaterialLength, MaterialProduct
from projects.models import Estimate, Project

from .calculations import generate_line_items
from .forms import AssemblyForm, ManualLineItemForm
from .models import Assembly, CalculationRule, LineItem

User = get_user_model()

_backfill_module = importlib.import_module('estimating.migrations.0012_backfill_categories')
backfill_categories = _backfill_module.backfill_categories
ASSEMBLY_CATEGORY_BY_NAME = _backfill_module.ASSEMBLY_CATEGORY_BY_NAME


class GenerateLineItemsCategoryTests(TestCase):
    def test_generate_line_items_sets_category_from_assembly(self):
        material = MaterialProduct.objects.create(name='Cat Stud', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=material, length_ft=16, is_default=True)
        assembly = Assembly.objects.create(
            name='Cat Test Wall', tool_type='line', category=Assembly.Category.WALL_SYSTEM,
        )
        CalculationRule.objects.create(
            assembly=assembly, material=material, role='Stud',
            formula_kind=CalculationRule.FormulaKind.PER_SPACING, extra=1, order=1,
        )
        user = User.objects.create_user(email='gen-cat@example.com', password='testpass123')
        project = Project.objects.create(account=user.account, name='Gen Cat House')
        estimate = Estimate.objects.create(project=project)

        items = generate_line_items(estimate, assembly, Decimal('20'), {'stud_spacing_in': 16})
        self.assertEqual(items[0].category, Assembly.Category.WALL_SYSTEM)


class BackfillMigrationTests(TestCase):
    def test_backfill_categorizes_known_global_assemblies(self):
        for name, expected_category in ASSEMBLY_CATEGORY_BY_NAME.items():
            assembly = Assembly.objects.get(name=name, account__isnull=True)
            self.assertEqual(assembly.category, expected_category, name)

    def test_backfill_function_sets_line_item_category_from_rule_assembly(self):
        class FakeApps:
            def get_model(self, app_label, model_name):
                return {'Assembly': Assembly, 'LineItem': LineItem}[model_name]

        material = MaterialProduct.objects.create(name='Backfill Stud', input_type=MaterialProduct.InputType.FT)
        assembly = Assembly.objects.create(
            name='2x6 Wall - 16 in OC', tool_type='line', account=Account.objects.create(name='Backfill Acct'),
            category=Assembly.Category.MISC,
        )
        rule = CalculationRule.objects.create(
            assembly=assembly, material=material, role='Stud',
            formula_kind=CalculationRule.FormulaKind.PER_SPACING, order=1,
        )
        project = Project.objects.create(account=assembly.account, name='Backfill House')
        estimate = Estimate.objects.create(project=project)
        line_item = LineItem.objects.create(
            estimate=estimate, calculation_rule=rule, material=material, role='Stud',
            quantity=9, category=Assembly.Category.MISC, source=LineItem.Source.TOOL,
        )
        # This account-owned assembly happens to share a name with a global
        # one; give it a real category to prove the backfill follows the
        # rule -> assembly link, not just the name map (which only touches
        # account__isnull=True rows).
        assembly.category = Assembly.Category.ROOF
        assembly.save(update_fields=['category'])

        backfill_categories(FakeApps(), None)

        line_item.refresh_from_db()
        self.assertEqual(line_item.category, Assembly.Category.ROOF)


class EstimateDetailGroupingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='group@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Group House')
        self.estimate = Estimate.objects.create(project=self.project)
        self.material = MaterialProduct.objects.create(name='Group Stud', input_type=MaterialProduct.InputType.FT)
        LineItem.objects.create(
            estimate=self.estimate, material=self.material, role='Stud', quantity=9,
            category=Assembly.Category.WALL_SYSTEM, source=LineItem.Source.TOOL,
        )
        LineItem.objects.create(
            estimate=self.estimate, material=self.material, role='Rafter', quantity=20,
            category=Assembly.Category.ROOF, source=LineItem.Source.TOOL,
        )
        self.client.force_login(self.user)

    def test_default_order_matches_doc_order(self):
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate.pk]))
        content = response.content.decode()
        # Doc order: Wall System comes before Roof.
        self.assertLess(content.index('Wall System'), content.index('>Roof<'))

    def test_saved_category_order_is_respected(self):
        self.user.account.category_order = ['roof', 'wall_system']
        self.user.account.save(update_fields=['category_order'])
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate.pk]))
        content = response.content.decode()
        self.assertLess(content.index('>Roof<'), content.index('Wall System'))

    def test_category_missing_from_saved_order_still_appears(self):
        self.user.account.category_order = ['wall_system']  # roof omitted
        self.user.account.save(update_fields=['category_order'])
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate.pk]))
        self.assertContains(response, '>Roof<')

    def test_item_order_is_case_and_whitespace_insensitive(self):
        LineItem.objects.create(
            estimate=self.estimate, material=self.material, role='Top Plate', quantity=4,
            category=Assembly.Category.WALL_SYSTEM, source=LineItem.Source.TOOL,
        )
        self.user.account.item_order = {'wall_system': ['  TOP PLATE  ', 'stud']}
        self.user.account.save(update_fields=['item_order'])
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate.pk]))
        content = response.content.decode()
        self.assertLess(content.index('Top Plate'), content.index('>Stud<'))


class CategoryOrderUpdateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='order-update@example.com', password='testpass123')
        self.other_user = User.objects.create_user(email='order-other@example.com', password='testpass123')
        self.client.force_login(self.user)

    def test_saves_valid_category_order(self):
        response = self.client.post(
            reverse('estimating:category-order-update'),
            data=json.dumps({'order': ['roof', 'wall_system']}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.account.refresh_from_db()
        self.assertEqual(self.user.account.category_order, ['roof', 'wall_system'])

    def test_rejects_unknown_category_key(self):
        response = self.client.post(
            reverse('estimating:category-order-update'),
            data=json.dumps({'order': ['not_a_real_category']}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_never_touches_another_accounts_order(self):
        self.client.post(
            reverse('estimating:category-order-update'),
            data=json.dumps({'order': ['roof']}), content_type='application/json',
        )
        self.other_user.account.refresh_from_db()
        self.assertEqual(self.other_user.account.category_order, [])


class ItemOrderUpdateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='item-order@example.com', password='testpass123')
        self.client.force_login(self.user)

    def test_saves_valid_item_order(self):
        response = self.client.post(
            reverse('estimating:item-order-update'),
            data=json.dumps({'category': 'wall_system', 'order': ['Top Plate', 'Stud']}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.account.refresh_from_db()
        self.assertEqual(self.user.account.item_order, {'wall_system': ['Top Plate', 'Stud']})

    def test_rejects_unknown_category(self):
        response = self.client.post(
            reverse('estimating:item-order-update'),
            data=json.dumps({'category': 'not_real', 'order': ['Stud']}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_saving_one_category_does_not_clobber_another(self):
        self.user.account.item_order = {'roof': ['Rafter']}
        self.user.account.save(update_fields=['item_order'])
        self.client.post(
            reverse('estimating:item-order-update'),
            data=json.dumps({'category': 'wall_system', 'order': ['Stud']}),
            content_type='application/json',
        )
        self.user.account.refresh_from_db()
        self.assertEqual(self.user.account.item_order, {'roof': ['Rafter'], 'wall_system': ['Stud']})


class ResetLayoutPreferencesViewTests(TestCase):
    def test_reset_clears_both_preferences(self):
        user = User.objects.create_user(email='reset-layout@example.com', password='testpass123')
        project = Project.objects.create(account=user.account, name='Reset House')
        estimate = Estimate.objects.create(project=project)
        user.account.category_order = ['roof']
        user.account.item_order = {'roof': ['Rafter']}
        user.account.save(update_fields=['category_order', 'item_order'])

        self.client.force_login(user)
        response = self.client.post(
            reverse('estimating:reset-layout-preferences'), data={'estimate_id': estimate.pk},
        )
        self.assertRedirects(response, reverse('estimating:estimate-detail', args=[estimate.pk]))
        user.account.refresh_from_db()
        self.assertEqual(user.account.category_order, [])
        self.assertEqual(user.account.item_order, {})


class ManualLineItemCategoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='manual-cat@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Manual Cat House')
        self.estimate = Estimate.objects.create(project=self.project)
        self.material = MaterialProduct.objects.create(name='Manual Cat Stud', input_type=MaterialProduct.InputType.FT)
        self.client.force_login(self.user)

    def test_category_defaults_to_misc_when_omitted(self):
        response = self.client.post(reverse('estimating:line-item-add', args=[self.estimate.pk]), data={
            'material': self.material.id, 'role': 'Extra', 'quantity': 2,
        })
        self.assertRedirects(response, reverse('estimating:estimate-detail', args=[self.estimate.pk]))
        line_item = LineItem.objects.get(estimate=self.estimate)
        self.assertEqual(line_item.category, Assembly.Category.MISC)

    def test_can_choose_a_category_explicitly(self):
        response = self.client.post(reverse('estimating:line-item-add', args=[self.estimate.pk]), data={
            'material': self.material.id, 'role': 'Stringer', 'quantity': 3, 'category': 'stairs',
        })
        self.assertRedirects(response, reverse('estimating:estimate-detail', args=[self.estimate.pk]))
        line_item = LineItem.objects.get(estimate=self.estimate)
        self.assertEqual(line_item.category, 'stairs')

    def test_manual_form_category_field_is_optional(self):
        form = ManualLineItemForm(data={'material': self.material.id, 'quantity': 1}, account=self.user.account)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['category'], Assembly.Category.MISC)


class AssemblyFormCategoryTests(TestCase):
    def test_category_is_optional_and_defaults_to_misc(self):
        form = AssemblyForm(data={'name': 'No Category Assembly', 'tool_type': 'line', 'description': ''})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['category'], Assembly.Category.MISC)

    def test_category_can_be_set_explicitly(self):
        form = AssemblyForm(data={
            'name': 'Roof Assembly', 'tool_type': 'area', 'category': 'roof', 'description': '',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['category'], 'roof')


class CsvExportCategoryTests(TestCase):
    def test_csv_includes_system_column_in_category_order(self):
        user = User.objects.create_user(email='csv-cat@example.com', password='testpass123')
        project = Project.objects.create(account=user.account, name='CSV Cat House')
        estimate = Estimate.objects.create(project=project)
        material = MaterialProduct.objects.create(name='CSV Cat Stud', input_type=MaterialProduct.InputType.FT)
        LineItem.objects.create(
            estimate=estimate, material=material, role='Rafter', quantity=10,
            category=Assembly.Category.ROOF, source=LineItem.Source.TOOL,
        )
        LineItem.objects.create(
            estimate=estimate, material=material, role='Stud', quantity=9,
            category=Assembly.Category.WALL_SYSTEM, source=LineItem.Source.TOOL,
        )

        EstimateAccessGrant.objects.create(
            estimate=estimate, purchased_by=user,
            status=EstimateAccessGrant.Status.PAID, stripe_checkout_session_id='cs_cat_paid',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('estimating:estimate-csv', args=[estimate.pk]))
        rows = list(csv.reader(response.content.decode().splitlines()))
        self.assertEqual(rows[0][0], 'System')
        # Wall System sorts before Roof per the doc default order.
        self.assertEqual(rows[1][0], 'Wall System')
        self.assertEqual(rows[2][0], 'Roof')
