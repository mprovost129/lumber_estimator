import csv
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
