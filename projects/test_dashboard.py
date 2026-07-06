from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import MaterialProduct
from estimating.models import LineItem
from plans.models import Trace
from plans.test_traces import make_plan_page

from .models import Project

User = get_user_model()


class DashboardTenancyTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email='a@example.com', password='testpass123')
        self.user_b = User.objects.create_user(email='b@example.com', password='testpass123')
        self.project_a = Project.objects.create(account=self.user_a.account, name='A House')
        self.project_b = Project.objects.create(account=self.user_b.account, name='B House')

    def test_signup_creates_distinct_personal_accounts(self):
        self.assertNotEqual(self.user_a.account_id, self.user_b.account_id)

    def test_dashboard_only_shows_own_account_projects(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('projects:dashboard'))
        self.assertContains(response, 'A House')
        self.assertNotContains(response, 'B House')

    def test_dashboard_excludes_archived_projects(self):
        self.project_a.status = Project.Status.ARCHIVED
        self.project_a.save()
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('projects:dashboard'))
        self.assertNotContains(response, 'A House')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('projects:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_renders_post_logout_form_and_logout_succeeds(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('projects:dashboard'))

        self.assertContains(response, 'action="/accounts/logout/"')
        self.assertContains(response, 'method="post"', html=False)

        logout_response = self.client.post(reverse('logout'))
        self.assertEqual(logout_response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_dashboard_shows_next_step_when_no_plans_uploaded(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('projects:dashboard'))

        self.assertContains(response, 'No plans uploaded')
        self.assertContains(response, 'Upload a PDF or image to start this takeoff.')

    def test_dashboard_shows_needs_calibration_when_page_uploaded_but_not_scaled(self):
        make_plan_page(self.project_a, label='Main Floor')
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('projects:dashboard'))

        self.assertContains(response, 'Needs calibration')

    def test_dashboard_shows_ready_to_trace_when_page_is_calibrated(self):
        page = make_plan_page(self.project_a, label='Main Floor')
        page.scale_pixels_per_foot = 12
        page.save(update_fields=['scale_pixels_per_foot'])
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('projects:dashboard'))

        self.assertContains(response, 'Ready to trace')

    def test_dashboard_shows_tracing_in_progress_when_traces_exist_without_materials(self):
        page = make_plan_page(self.project_a, label='Main Floor')
        page.scale_pixels_per_foot = 12
        page.save(update_fields=['scale_pixels_per_foot'])
        Trace.objects.create(
            plan_page=page, tool_type=Trace.ToolType.COUNT, geometry=[{'x': 1, 'y': 1}],
        )
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('projects:dashboard'))

        self.assertContains(response, 'Tracing in progress')

    def test_dashboard_shows_estimate_ready_when_line_items_exist(self):
        estimate = self.project_a.get_or_create_estimate()
        material = MaterialProduct.objects.create(name='Dashboard Stud', input_type=MaterialProduct.InputType.FT)
        LineItem.objects.create(
            estimate=estimate,
            material=material,
            role='Stud',
            quantity=5,
            source=LineItem.Source.MANUAL,
        )
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('projects:dashboard'))

        self.assertContains(response, 'Estimate ready')
