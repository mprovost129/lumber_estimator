import os
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import MaterialLength, MaterialProduct
from estimating.models import Assembly, CalculationRule, LineItem
from projects.models import Estimate, JobSettings, Project

from .models import Plan, PlanPage, Trace
from .test_traces import make_plan_page

User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PlanPageDeleteViewTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email='page-del-a@example.com', password='testpass123')
        self.user_b = User.objects.create_user(email='page-del-b@example.com', password='testpass123')
        self.project_a = Project.objects.create(account=self.user_a.account, name='Page Del A House')
        self.project_b = Project.objects.create(account=self.user_b.account, name='Page Del B House')
        JobSettings.objects.create(project=self.project_a)
        JobSettings.objects.create(project=self.project_b)
        self.page = make_plan_page(self.project_a)

    def test_deletes_the_page(self):
        self.client.force_login(self.user_a)
        response = self.client.post(reverse('plans:page-delete', args=[self.page.pk]))
        self.assertRedirects(response, reverse('projects:detail', args=[self.project_a.pk]))
        self.assertFalse(PlanPage.objects.filter(pk=self.page.pk).exists())

    def test_deleting_a_page_removes_its_image_and_thumbnail_files(self):
        image_path = self.page.image.path
        thumbnail_path = self.page.thumbnail.path
        self.assertTrue(os.path.exists(image_path))
        self.assertTrue(os.path.exists(thumbnail_path))

        self.client.force_login(self.user_a)
        self.client.post(reverse('plans:page-delete', args=[self.page.pk]))

        self.assertFalse(os.path.exists(image_path))
        self.assertFalse(os.path.exists(thumbnail_path))

    def test_deleting_a_page_cascades_traces_and_line_items(self):
        estimate = Estimate.objects.create(project=self.project_a)
        material = MaterialProduct.objects.create(name='Page Del Stud', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=material, length_ft=16, is_default=True)
        assembly = Assembly.objects.create(name='Page Del Wall', tool_type='line')
        CalculationRule.objects.create(
            assembly=assembly, material=material, role='Stud',
            formula_kind=CalculationRule.FormulaKind.PER_SPACING, order=1,
        )
        trace = Trace.objects.create(
            plan_page=self.page, tool_type='line', geometry=[{'x': 0, 'y': 0}, {'x': 10, 'y': 0}],
        )
        LineItem.objects.create(
            estimate=estimate, trace=trace, material=material, role='Stud', quantity=5,
            source=LineItem.Source.TOOL,
        )

        self.client.force_login(self.user_a)
        self.client.post(reverse('plans:page-delete', args=[self.page.pk]))

        self.assertFalse(Trace.objects.filter(pk=trace.pk).exists())
        self.assertFalse(LineItem.objects.filter(trace_id=trace.pk).exists())

    def test_cannot_delete_other_accounts_page(self):
        self.client.force_login(self.user_b)
        response = self.client.post(reverse('plans:page-delete', args=[self.page.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(PlanPage.objects.filter(pk=self.page.pk).exists())

    def test_requires_login(self):
        response = self.client.post(reverse('plans:page-delete', args=[self.page.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlanPage.objects.filter(pk=self.page.pk).exists())

    def test_deleting_the_only_page_leaves_the_plan_intact_with_no_pages(self):
        # Deleting a page doesn't remove the Plan container itself - a user
        # might still be trimming unwanted pages from an otherwise-kept import.
        self.client.force_login(self.user_a)
        plan_id = self.page.plan_id
        self.client.post(reverse('plans:page-delete', args=[self.page.pk]))
        self.assertTrue(Plan.objects.filter(pk=plan_id).exists())
        self.assertEqual(PlanPage.objects.filter(plan_id=plan_id).count(), 0)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PlanPageLabelUpdateTests(TestCase):
    """The label endpoint serves two callers: the project detail's plain form
    (redirect back, unchanged) and the viewer's inline rename over fetch
    (answers JSON when the XHR header is present)."""

    def setUp(self):
        self.user = User.objects.create_user(email='label-a@example.com', password='testpass123')
        self.other = User.objects.create_user(email='label-b@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Label House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.url = reverse('plans:page-label', args=[self.page.pk])

    def test_plain_form_post_updates_and_redirects(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'label': 'First Floor'})
        self.assertRedirects(response, reverse('projects:detail', args=[self.project.pk]))
        self.page.refresh_from_db()
        self.assertEqual(self.page.label, 'First Floor')

    def test_ajax_post_updates_and_returns_json(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, {'label': 'Second Floor'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['label'], 'Second Floor')
        self.assertEqual(data['display_label'], 'Second Floor')
        self.page.refresh_from_db()
        self.assertEqual(self.page.label, 'Second Floor')

    def test_ajax_blank_label_falls_back_to_page_number_display(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'label': '   '}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = response.json()
        self.assertEqual(data['label'], '')
        self.assertEqual(data['display_label'], f'Page {self.page.page_number}')

    def test_other_account_404s(self):
        self.client.force_login(self.other)
        response = self.client.post(self.url, {'label': 'Hijack'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 404)
