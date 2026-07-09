import csv
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from billing.models import AccountSubscription, EstimateAccessGrant
from catalog.models import MaterialLength, MaterialProduct
from plans.models import Trace
from plans.test_traces import make_plan_page
from projects.models import Estimate, Project

from .models import LineItem, MaterialGroup

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

    def test_tool_generated_line_links_back_to_source_trace(self):
        page = make_plan_page(self.project_a, label='First Floor')
        trace = Trace.objects.create(
            plan_page=page, tool_type=Trace.ToolType.LINE, geometry=[{'x': 0, 'y': 0}, {'x': 10, 'y': 0}],
        )
        LineItem.objects.create(
            estimate=self.estimate_a, material=self.material, trace=trace, role='Plate', quantity=2,
            source=LineItem.Source.TOOL,
        )

        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate_a.pk]))

        self.assertContains(response, f'{reverse("plans:viewer", args=[page.pk])}?trace={trace.pk}')

    def test_locked_estimate_shows_unlock_actions(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate_a.pk]))
        self.assertContains(response, 'Unlock export + print')
        self.assertNotContains(response, 'Download CSV')

    def test_active_subscription_restores_export_actions(self):
        AccountSubscription.objects.create(
            account=self.user_a.account,
            stripe_subscription_id='sub_123',
            plan_slug='starter',
            status=AccountSubscription.Status.ACTIVE,
        )
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate_a.pk]))
        self.assertContains(response, 'Download CSV')
        self.assertContains(response, 'Print-friendly view')

    def test_group_waste_editor_renders_for_grouped_tool_line(self):
        group, _ = MaterialGroup.objects.get_or_create(
            name='Exterior Studs', defaults={'default_waste_factor': Decimal('0.10')},
        )
        item = LineItem.objects.create(
            estimate=self.estimate_a,
            material=self.material,
            material_group=group,
            role='Stud',
            quantity=9,
            waste_factor=Decimal('0.10'),
            source=LineItem.Source.TOOL,
        )

        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate_a.pk]))
        self.assertContains(response, 'Exterior Studs')
        self.assertContains(
            response,
            reverse('estimating:estimate-material-group-waste', args=[self.estimate_a.pk, group.pk]),
        )


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

    def test_summary_shows_material_group_and_waste_editor(self):
        group, _ = MaterialGroup.objects.get_or_create(
            name='Wall Sheathing', defaults={'default_waste_factor': Decimal('0.10')},
        )
        LineItem.objects.create(
            estimate=self.estimate_a,
            material=self.material,
            material_group=group,
            role='Sheathing',
            quantity=12,
            waste_factor=Decimal('0.10'),
            source=LineItem.Source.TOOL,
        )
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-material-summary', args=[self.estimate_a.pk]))
        self.assertContains(response, 'Group: Wall Sheathing')
        self.assertContains(
            response,
            reverse('estimating:estimate-material-group-waste', args=[self.estimate_a.pk, group.pk]),
        )


class EstimateMaterialGroupWasteUpdateViewTests(TestCase):
    def setUp(self):
        from estimating.models import Assembly, CalculationRule

        self.user = User.objects.create_user(email='waste@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Waste House')
        self.estimate = Estimate.objects.create(project=self.project)
        self.material = MaterialProduct.objects.create(
            name='Waste Stud', input_type=MaterialProduct.InputType.FT,
        )
        MaterialLength.objects.create(product=self.material, length_ft=Decimal('8'), is_default=True)
        self.group, _ = MaterialGroup.objects.get_or_create(
            name='Exterior Studs', defaults={'default_waste_factor': Decimal('0.10')},
        )
        self.assembly = Assembly.objects.create(
            account=self.user.account, name='Waste Wall', tool_type='line', category='wall_system',
            wall_subtype='exterior',
        )
        self.rule = CalculationRule.objects.create(
            assembly=self.assembly,
            material=self.material,
            material_group=self.group,
            role='Stud',
            formula_kind=CalculationRule.FormulaKind.PER_SPACING,
            extra=1,
            waste_factor=Decimal('0.10'),
            order=1,
        )
        self.page = make_plan_page(self.project, label='Waste Page')
        self.page.scale_pixels_per_foot = Decimal('10')
        self.page.save(update_fields=['scale_pixels_per_foot'])
        self.trace = Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
            assembly=self.assembly,
            settings={'stud_spacing_in': 16, 'wall_height_in': 96},
        )
        LineItem.objects.create(
            estimate=self.estimate,
            trace=self.trace,
            calculation_rule=self.rule,
            material=self.material,
            material_group=self.group,
            role='Stud',
            quantity=9,
            waste_factor=Decimal('0.10'),
            source=LineItem.Source.TOOL,
        )
        self.client.force_login(self.user)

    def test_updates_estimate_group_waste_and_recalculates_linked_traces(self):
        response = self.client.post(
            reverse('estimating:estimate-material-group-waste', args=[self.estimate.pk, self.group.pk]),
            data=json.dumps({'waste_percent': '20'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        item = LineItem.objects.get(estimate=self.estimate, trace=self.trace)
        self.assertEqual(item.material_group_id, self.group.pk)
        self.assertEqual(item.waste_factor, Decimal('0.200'))
        self.assertEqual(item.quantity, 11)

    def test_requires_same_account_estimate(self):
        other = User.objects.create_user(email='waste-other@example.com', password='testpass123')
        other_project = Project.objects.create(account=other.account, name='Other Waste House')
        other_estimate = Estimate.objects.create(project=other_project)
        response = self.client.post(
            reverse('estimating:estimate-material-group-waste', args=[other_estimate.pk, self.group.pk]),
            data=json.dumps({'waste_percent': '20'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)


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
        EstimateAccessGrant.objects.create(
            estimate=self.estimate_a,
            purchased_by=self.user_a,
            status=EstimateAccessGrant.Status.PAID,
            stripe_checkout_session_id='cs_paid',
        )
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
        EstimateAccessGrant.objects.create(
            estimate=self.estimate_a,
            purchased_by=self.user_a,
            status=EstimateAccessGrant.Status.PAID,
            stripe_checkout_session_id='cs_other',
        )
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-csv', args=[self.estimate_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_requires_login(self):
        response = self.client.get(reverse('estimating:estimate-csv', args=[self.estimate_a.pk]))
        self.assertEqual(response.status_code, 302)

    def test_locked_export_redirects_back_to_estimate(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('estimating:estimate-csv', args=[self.estimate_a.pk]))
        self.assertRedirects(response, reverse('estimating:estimate-detail', args=[self.estimate_a.pk]))


class EstimatePrintViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='print@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Print House')
        self.estimate = Estimate.objects.create(project=self.project)
        self.material = MaterialProduct.objects.create(
            name='Print Stud', input_type=MaterialProduct.InputType.FT,
        )
        LineItem.objects.create(
            estimate=self.estimate, material=self.material, role='Stud', quantity=8,
            source=LineItem.Source.TOOL,
        )

    def test_locked_print_redirects(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('estimating:estimate-print', args=[self.estimate.pk]))
        self.assertRedirects(response, reverse('estimating:estimate-detail', args=[self.estimate.pk]))

    def test_unlocked_print_renders(self):
        EstimateAccessGrant.objects.create(
            estimate=self.estimate,
            purchased_by=self.user,
            status=EstimateAccessGrant.Status.PAID,
            stripe_checkout_session_id='cs_print',
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('estimating:estimate-print', args=[self.estimate.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Print now')
        self.assertContains(response, 'Print Stud')


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


class MaterialLibraryManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='materials-a@example.com', password='testpass123')
        self.other = User.objects.create_user(email='materials-b@example.com', password='testpass123')
        self.client.force_login(self.user)
        self.mine = MaterialProduct.objects.create(
            account=self.user.account,
            name='My Plate Stock',
            category=MaterialProduct.Category.DIMENSIONAL,
            input_type=MaterialProduct.InputType.FT,
        )
        MaterialLength.objects.create(product=self.mine, length_ft=Decimal('8'), is_default=True)
        MaterialLength.objects.create(product=self.mine, length_ft=Decimal('16'))
        self.foreign = MaterialProduct.objects.create(
            account=self.other.account, name='Foreign Material', input_type=MaterialProduct.InputType.EACH,
        )
        self.stock = MaterialProduct.objects.create(name='Stock Material', input_type=MaterialProduct.InputType.EACH)

    def test_user_can_create_material_from_library_form(self):
        response = self.client.post(
            reverse('estimating:material-create'),
            {
                'name': 'Custom Connector',
                'category': MaterialProduct.Category.CONNECTORS,
                'species': '',
                'grade': '',
                'nominal_dimension': '',
                'supported_input_types': [MaterialProduct.InputType.BOX, MaterialProduct.InputType.EACH],
                'input_type': MaterialProduct.InputType.BOX,
                'quantity_per_box': '150',
                'lengths': '',
                'default_length': '',
            },
            follow=True,
        )
        self.assertRedirects(response, reverse('estimating:library'))
        created = MaterialProduct.objects.get(account=self.user.account, name='Custom Connector')
        self.assertEqual(created.quantity_per_box, 150)
        self.assertEqual(
            created.normalized_supported_input_types(),
            [MaterialProduct.InputType.BOX, MaterialProduct.InputType.EACH],
        )
        self.assertContains(response, 'Custom Connector')
        self.assertContains(response, 'created.')

    def test_user_can_edit_owned_material_and_lengths(self):
        response = self.client.post(
            reverse('estimating:material-update', args=[self.mine.pk]),
            {
                'name': 'My Plate Stock Updated',
                'category': MaterialProduct.Category.PRESSURE_TREATED,
                'species': 'SPF',
                'grade': '#2',
                'nominal_dimension': '2x6',
                'supported_input_types': [MaterialProduct.InputType.FT, MaterialProduct.InputType.EACH],
                'input_type': MaterialProduct.InputType.FT,
                'quantity_per_box': '',
                'lengths': '10; 18',
                'default_length': '18',
            },
            follow=True,
        )
        self.assertRedirects(response, reverse('estimating:library'))
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.name, 'My Plate Stock Updated')
        self.assertEqual(self.mine.category, MaterialProduct.Category.PRESSURE_TREATED)
        self.assertEqual(
            self.mine.normalized_supported_input_types(),
            [MaterialProduct.InputType.FT, MaterialProduct.InputType.EACH],
        )
        self.assertEqual(
            list(self.mine.lengths.order_by('length_ft').values_list('length_ft', flat=True)),
            [Decimal('10'), Decimal('18')],
        )
        self.assertEqual(self.mine.default_length_ft, Decimal('18'))

    def test_edit_rejects_default_length_not_in_stock_lengths(self):
        response = self.client.post(
            reverse('estimating:material-update', args=[self.mine.pk]),
            {
                'name': 'My Plate Stock',
                'category': MaterialProduct.Category.DIMENSIONAL,
                'species': '',
                'grade': '',
                'nominal_dimension': '',
                'supported_input_types': [MaterialProduct.InputType.FT],
                'input_type': MaterialProduct.InputType.FT,
                'quantity_per_box': '',
                'lengths': '8, 16',
                'default_length': '12',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Default length must be one of the listed stock lengths.')

    def test_user_can_delete_unused_owned_material(self):
        response = self.client.post(
            reverse('estimating:material-delete', args=[self.mine.pk]),
            follow=True,
        )
        self.assertRedirects(response, reverse('estimating:library'))
        self.assertFalse(MaterialProduct.objects.filter(pk=self.mine.pk).exists())
        self.assertContains(response, 'My Plate Stock')
        self.assertContains(response, 'deleted.')

    def test_delete_shows_message_when_material_is_in_use(self):
        project = Project.objects.create(account=self.user.account, name='Delete Guard Project')
        estimate = Estimate.objects.create(project=project)
        LineItem.objects.create(
            estimate=estimate, material=self.mine, role='Plate', quantity=2, source=LineItem.Source.MANUAL,
        )
        response = self.client.post(
            reverse('estimating:material-delete', args=[self.mine.pk]),
            follow=True,
        )
        self.assertRedirects(response, reverse('estimating:library'))
        self.assertTrue(MaterialProduct.objects.filter(pk=self.mine.pk).exists())
        self.assertContains(response, 'My Plate Stock')
        self.assertContains(response, 'because it is still used')

    def test_user_cannot_edit_or_delete_stock_or_foreign_materials(self):
        self.assertEqual(
            self.client.get(reverse('estimating:material-update', args=[self.stock.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse('estimating:material-update', args=[self.foreign.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('estimating:material-delete', args=[self.stock.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('estimating:material-delete', args=[self.foreign.pk])).status_code,
            404,
        )


class AssemblyQuickEditTests(TestCase):
    """The Library drawer endpoint. Copy-on-write on global assemblies; edits
    in place on account-owned ones; strict validation of materials and groups."""

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
        self.group, _ = MaterialGroup.objects.get_or_create(
            name='Exterior Studs', defaults={'default_waste_factor': Decimal('0.10')},
        )
        self.group_alt, _ = MaterialGroup.objects.get_or_create(
            name='Exterior Plates', defaults={'default_waste_factor': Decimal('0.05')},
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
            material_group=self.group, waste_factor=Decimal('0.05'),
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
        self.assertEqual(data['rules'][0]['material_group_id'], self.group.pk)

    def test_editing_global_assembly_clones_into_account(self):
        from estimating.models import Assembly

        response = self._post(self.global_assembly, [
            {'id': self.rule.pk, 'material_id': self.material_alt.pk, 'material_group_id': self.group_alt.pk},
        ])
        data = response.json()
        self.assertTrue(data['cloned'])
        clone = Assembly.objects.get(pk=data['id'])
        self.assertEqual(clone.account_id, self.user.account_id)
        self.assertEqual(clone.name, 'QE Global Wall (Custom)')
        self.assertFalse(clone.is_default)
        clone_rule = clone.rules.get()
        self.assertEqual(clone_rule.material_id, self.material_alt.pk)
        self.assertEqual(clone_rule.material_group_id, self.group_alt.pk)
        # The global source is untouched for every other tenant.
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.material_id, self.material.pk)
        self.assertEqual(self.rule.material_group_id, self.group.pk)

    def test_second_edit_reuses_the_clone(self):
        from estimating.models import Assembly

        first = self._post(self.global_assembly, [
            {'id': self.rule.pk, 'material_id': self.material_alt.pk, 'material_group_id': self.group_alt.pk},
        ]).json()
        second = self._post(self.global_assembly, [
            {'id': self.rule.pk, 'material_id': self.material.pk, 'material_group_id': self.group.pk},
        ]).json()
        self.assertFalse(second['cloned'])
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(
            Assembly.objects.filter(account=self.user.account, name__startswith='QE Global Wall').count(), 1,
        )
        clone_rule = Assembly.objects.get(pk=second['id']).rules.get()
        self.assertEqual(clone_rule.material_group_id, self.group.pk)

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
            {'id': owned_rule.pk, 'material_id': self.material_alt.pk, 'material_group_id': self.group_alt.pk},
        ])
        self.assertFalse(response.json()['cloned'])
        owned_rule.refresh_from_db()
        self.assertEqual(owned_rule.material_id, self.material_alt.pk)
        self.assertEqual(owned_rule.material_group_id, self.group_alt.pk)

    def test_rejects_foreign_material_and_bad_group(self):
        response = self._post(self.global_assembly, [
            {'id': self.rule.pk, 'material_id': self.foreign_material.pk, 'material_group_id': self.group.pk},
        ])
        self.assertEqual(response.status_code, 400)
        response = self._post(self.global_assembly, [
            {'id': self.rule.pk, 'material_id': self.material.pk, 'material_group_id': 999999},
        ])
        self.assertEqual(response.status_code, 400)

    def test_other_accounts_custom_assembly_404s(self):
        from estimating.models import Assembly

        foreign = Assembly.objects.create(
            account=self.other.account, name='QE Foreign Asm', tool_type='line',
        )
        self.assertEqual(self.client.get(self._url(foreign)).status_code, 404)
