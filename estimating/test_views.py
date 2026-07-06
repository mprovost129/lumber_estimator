import csv
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import MaterialProduct
from projects.models import Estimate, Project

from .models import LineItem

User = get_user_model()


class EstimateDetailViewTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email='est-a@example.com', password='testpass123')
        self.user_b = User.objects.create_user(email='est-b@example.com', password='testpass123')
        self.project_a = Project.objects.create(account=self.user_a.account, name='Estimate A House')
        self.project_b = Project.objects.create(account=self.user_b.account, name='Estimate B House')
        self.estimate_a = Estimate.objects.create(project=self.project_a)
        self.estimate_b = Estimate.objects.create(project=self.project_b)

        self.material = MaterialProduct.objects.create(
            name='Estimate View Stud', input_type=MaterialProduct.InputType.FT,
        )
        LineItem.objects.create(
            estimate=self.estimate_a, material=self.material, role='Stud', quantity=9,
            source=LineItem.Source.TOOL,
        )

    def test_renders_own_estimate_line_items(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Estimate View Stud')
        self.assertContains(response, '9')

    def test_cannot_view_other_accounts_estimate(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_requires_login(self):
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate_a.pk]))
        self.assertEqual(response.status_code, 302)


class EstimateMaterialSummaryViewTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email='matsum-a@example.com', password='testpass123')
        self.user_b = User.objects.create_user(email='matsum-b@example.com', password='testpass123')
        self.project_a = Project.objects.create(account=self.user_a.account, name='Material Summary A House')
        self.project_b = Project.objects.create(account=self.user_b.account, name='Material Summary B House')
        self.estimate_a = Estimate.objects.create(project=self.project_a)
        self.estimate_b = Estimate.objects.create(project=self.project_b)

        self.material = MaterialProduct.objects.create(
            name='Material Summary Stud', input_type=MaterialProduct.InputType.FT,
        )

    def test_renders_grouped_materials(self):
        LineItem.objects.create(
            estimate=self.estimate_a, material=self.material, role='Stud', quantity=12,
            source=LineItem.Source.TOOL,
        )
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-material-summary', args=[self.estimate_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'estimating/_material_summary.html')
        self.assertContains(response, 'Material Summary Stud')
        self.assertContains(response, '12')

    def test_empty_state(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-material-summary', args=[self.estimate_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No materials yet')

    def test_cannot_view_other_accounts_estimate(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-material-summary', args=[self.estimate_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_requires_login(self):
        response = self.client.get(reverse('estimating:estimate-material-summary', args=[self.estimate_a.pk]))
        self.assertEqual(response.status_code, 302)

    def test_summary_stats_bar_totals(self):
        # Framing BF counts only plain NxM dimensions with a piece length:
        # 10 pieces of 2x6 @ 16 ft = 2 * 6 * 16 / 12 * 10 = 160 BF. The sheet
        # good (three-part dimension, no length) adds pieces but no BF.
        framing = MaterialProduct.objects.create(
            name='Summary 2x6', input_type=MaterialProduct.InputType.FT, nominal_dimension='2x6',
        )
        sheet = MaterialProduct.objects.create(
            name='Summary OSB', input_type=MaterialProduct.InputType.EACH, nominal_dimension='7/16x4x8',
        )
        LineItem.objects.create(
            estimate=self.estimate_a, material=framing, role='Stud', quantity=10,
            length_ft=Decimal('16'), source=LineItem.Source.TOOL,
        )
        LineItem.objects.create(
            estimate=self.estimate_a, material=sheet, role='Sheathing', quantity=25,
            source=LineItem.Source.TOOL,
        )
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-material-summary', args=[self.estimate_a.pk]))
        totals = response.context['totals']
        self.assertEqual(totals['total_pieces'], 35)
        self.assertEqual(totals['row_count'], 2)
        self.assertEqual(totals['framing_bf'], Decimal('160'))
        self.assertContains(response, 'mat-summary-stats')
        self.assertContains(response, 'framing BF')

    def test_summary_stats_bar_hidden_when_empty(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-material-summary', args=[self.estimate_a.pk]))
        self.assertNotContains(response, 'mat-summary-stats')


class EstimateCsvExportViewTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email='csv-a@example.com', password='testpass123')
        self.user_b = User.objects.create_user(email='csv-b@example.com', password='testpass123')
        self.project_a = Project.objects.create(account=self.user_a.account, name='CSV A House')
        self.project_b = Project.objects.create(account=self.user_b.account, name='CSV B House')
        self.estimate_a = Estimate.objects.create(project=self.project_a)
        self.estimate_b = Estimate.objects.create(project=self.project_b)

        self.material = MaterialProduct.objects.create(
            name='CSV Test Stud', species='SPF', grade='#2', nominal_dimension='2x6',
            input_type=MaterialProduct.InputType.FT,
        )
        LineItem.objects.create(
            estimate=self.estimate_a, material=self.material, role='Stud',
            length_ft=Decimal('8.00'), quantity=9, source=LineItem.Source.TOOL,
        )
        LineItem.objects.create(
            estimate=self.estimate_a, material=self.material, role='Stud',
            length_ft=Decimal('8.00'), quantity=5, source=LineItem.Source.MANUAL,
        )

    def test_csv_groups_and_sums_matching_lines(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-csv', args=[self.estimate_a.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])

        rows = list(csv.reader(response.content.decode().splitlines()))
        self.assertEqual(rows[0], ['System', 'Material', 'Dimension', 'Species/Grade', 'Length (ft)', 'Quantity'])
        # Both LineItems share category + material + length_ft, so they're grouped into one row summing to 14.
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], 'Miscellaneous')
        self.assertEqual(rows[1][1], 'CSV Test Stud')
        self.assertEqual(rows[1][5], '14')

    def test_cannot_export_other_accounts_estimate(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-csv', args=[self.estimate_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_requires_login(self):
        response = self.client.get(reverse('estimating:estimate-csv', args=[self.estimate_a.pk]))
        self.assertEqual(response.status_code, 302)


class ManualLineItemViewTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email='manual-a@example.com', password='testpass123')
        self.user_b = User.objects.create_user(email='manual-b@example.com', password='testpass123')
        self.project_a = Project.objects.create(account=self.user_a.account, name='Manual A House')
        self.project_b = Project.objects.create(account=self.user_b.account, name='Manual B House')
        self.estimate_a = Estimate.objects.create(project=self.project_a)
        self.estimate_b = Estimate.objects.create(project=self.project_b)
        self.material = MaterialProduct.objects.create(
            name='Manual Test Stud', input_type=MaterialProduct.InputType.FT,
        )

    def test_add_manual_line_item(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('estimating:line-item-add', args=[self.estimate_a.pk]),
            data={'material': self.material.id, 'role': 'Extra studs', 'quantity': 3},
        )
        self.assertRedirects(response, reverse('estimating:estimate-detail', args=[self.estimate_a.pk]))
        line_item = LineItem.objects.get(estimate=self.estimate_a)
        self.assertEqual(line_item.quantity, 3)
        self.assertEqual(line_item.source, LineItem.Source.MANUAL)

    def test_cannot_add_line_to_other_accounts_estimate(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('estimating:line-item-add', args=[self.estimate_b.pk]),
            data={'material': self.material.id, 'role': 'Extra studs', 'quantity': 3},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(LineItem.objects.exists())

    def test_delete_manual_line_item(self):
        line_item = LineItem.objects.create(
            estimate=self.estimate_a, material=self.material, role='Extra', quantity=2,
            source=LineItem.Source.MANUAL,
        )
        self.client.force_login(self.user_a)
        response = self.client.post(reverse('estimating:line-item-delete', args=[line_item.pk]))
        self.assertRedirects(response, reverse('estimating:estimate-detail', args=[self.estimate_a.pk]))
        self.assertFalse(LineItem.objects.filter(pk=line_item.pk).exists())

    def test_cannot_delete_tool_generated_line_item(self):
        line_item = LineItem.objects.create(
            estimate=self.estimate_a, material=self.material, role='Stud', quantity=9,
            source=LineItem.Source.TOOL,
        )
        self.client.force_login(self.user_a)
        response = self.client.post(reverse('estimating:line-item-delete', args=[line_item.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(LineItem.objects.filter(pk=line_item.pk).exists())

    def test_cannot_delete_other_accounts_line_item(self):
        line_item = LineItem.objects.create(
            estimate=self.estimate_b, material=self.material, role='Extra', quantity=2,
            source=LineItem.Source.MANUAL,
        )
        self.client.force_login(self.user_a)
        response = self.client.post(reverse('estimating:line-item-delete', args=[line_item.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(LineItem.objects.filter(pk=line_item.pk).exists())


class AssemblyQuickEditTests(TestCase):
    """The Library drawer endpoint. Copy-on-write on global assemblies; edits
    in place on account-owned ones; strict validation of materials and waste."""

    def setUp(self):
        from estimating.models import Assembly, CalculationRule

        self.user = User.objects.create_user(email='qe-a@example.com', password='testpass123')
        self.other = User.objects.create_user(email='qe-b@example.com', password='testpass123')
        self.material = MaterialProduct.objects.create(
            name='QE 2x6', input_type=MaterialProduct.InputType.FT, nominal_dimension='2x6',
        )
        self.material_alt = MaterialProduct.objects.create(
            name='QE 2x8', input_type=MaterialProduct.InputType.FT, nominal_dimension='2x8',
        )
        self.foreign_material = MaterialProduct.objects.create(
            account=self.other.account, name='QE Foreign', input_type=MaterialProduct.InputType.FT,
        )
        self.global_assembly = Assembly.objects.create(
            name='QE Global Wall', tool_type='line', category='wall_system',
        )
        self.rule = CalculationRule.objects.create(
            assembly=self.global_assembly, material=self.material, role='Stud',
            formula_kind=CalculationRule.FormulaKind.PER_SPACING, order=1,
            waste_factor=Decimal('0.05'),
        )
        self.client.force_login(self.user)

    def _url(self, assembly):
        return reverse('estimating:assembly-quick-edit', args=[assembly.pk])

    def _post(self, assembly, rules):
        return self.client.post(
            self._url(assembly), data=json.dumps({'rules': rules}),
            content_type='application/json',
        )

    def test_get_returns_rules(self):
        response = self.client.get(self._url(self.global_assembly))
        data = response.json()
        self.assertTrue(data['is_global'])
        self.assertEqual(data['rules'][0]['role'], 'Stud')
        self.assertEqual(data['rules'][0]['material_id'], self.material.pk)

    def test_editing_global_assembly_clones_into_account(self):
        from estimating.models import Assembly

        response = self._post(self.global_assembly, [
            {'id': self.rule.pk, 'material_id': self.material_alt.pk, 'waste_factor': '0.100'},
        ])
        data = response.json()
        self.assertTrue(data['cloned'])
        clone = Assembly.objects.get(pk=data['id'])
        self.assertEqual(clone.account_id, self.user.account_id)
        self.assertEqual(clone.name, 'QE Global Wall (Custom)')
        self.assertFalse(clone.is_default)
        clone_rule = clone.rules.get()
        self.assertEqual(clone_rule.material_id, self.material_alt.pk)
        self.assertEqual(clone_rule.waste_factor, Decimal('0.100'))
        # The global source is untouched for every other tenant.
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.material_id, self.material.pk)
        self.assertEqual(self.rule.waste_factor, Decimal('0.050'))

    def test_second_edit_reuses_the_clone(self):
        from estimating.models import Assembly

        first = self._post(self.global_assembly, [
            {'id': self.rule.pk, 'material_id': self.material_alt.pk, 'waste_factor': '0.100'},
        ]).json()
        second = self._post(self.global_assembly, [
            {'id': self.rule.pk, 'material_id': self.material.pk, 'waste_factor': '0.150'},
        ]).json()
        self.assertFalse(second['cloned'])
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(
            Assembly.objects.filter(account=self.user.account, name__startswith='QE Global Wall').count(), 1,
        )
        clone_rule = Assembly.objects.get(pk=second['id']).rules.get()
        self.assertEqual(clone_rule.waste_factor, Decimal('0.150'))

    def test_editing_owned_assembly_updates_in_place(self):
        from estimating.models import Assembly, CalculationRule

        owned = Assembly.objects.create(
            account=self.user.account, name='QE Mine', tool_type='line', category='wall_system',
        )
        owned_rule = CalculationRule.objects.create(
            assembly=owned, material=self.material, role='Plate',
            formula_kind=CalculationRule.FormulaKind.PER_STOCK_LENGTH, order=1,
        )
        response = self._post(owned, [
            {'id': owned_rule.pk, 'material_id': self.material_alt.pk, 'waste_factor': '0.050'},
        ])
        self.assertFalse(response.json()['cloned'])
        owned_rule.refresh_from_db()
        self.assertEqual(owned_rule.material_id, self.material_alt.pk)

    def test_rejects_foreign_material_and_bad_waste(self):
        response = self._post(self.global_assembly, [
            {'id': self.rule.pk, 'material_id': self.foreign_material.pk, 'waste_factor': '0.100'},
        ])
        self.assertEqual(response.status_code, 400)
        response = self._post(self.global_assembly, [
            {'id': self.rule.pk, 'material_id': self.material.pk, 'waste_factor': '1.5'},
        ])
        self.assertEqual(response.status_code, 400)

    def test_other_accounts_custom_assembly_404s(self):
        from estimating.models import Assembly

        foreign = Assembly.objects.create(
            account=self.other.account, name='QE Foreign Asm', tool_type='line',
        )
        self.assertEqual(self.client.get(self._url(foreign)).status_code, 404)
