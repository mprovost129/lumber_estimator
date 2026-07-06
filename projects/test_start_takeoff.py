import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from plans.models import Trace
from plans.test_traces import make_plan_page

from .models import JobSettings, Project

User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StartTakeoffTests(TestCase):
    """One-click 'Start Takeoff': lands on the last-worked page (most recent
    trace), else the first page of the newest plan, else back to the project
    with a prompt to upload a plan."""

    def setUp(self):
        self.user = User.objects.create_user(email='a@example.com', password='testpass123')
        self.other = User.objects.create_user(email='b@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='A House')
        JobSettings.objects.create(project=self.project)
        self.client.force_login(self.user)

    def _url(self, project=None):
        return reverse('projects:start-takeoff', args=[(project or self.project).pk])

    def test_no_plans_redirects_back_to_project_with_prompt(self):
        response = self.client.get(self._url(), follow=True)
        self.assertRedirects(response, reverse('projects:detail', args=[self.project.pk]))
        self.assertContains(response, 'Upload a plan first')

    def test_plan_without_traces_goes_to_first_page_of_newest_plan(self):
        older_page = make_plan_page(self.project, label='Old Plan Page')
        newer_page = make_plan_page(self.project, label='New Plan Page')
        # make_plan_page creates one plan per call; the second is the newest.
        self.assertGreater(newer_page.plan.uploaded_at, older_page.plan.uploaded_at)
        response = self.client.get(self._url())
        self.assertRedirects(response, reverse('plans:viewer', args=[newer_page.pk]))

    def test_with_traces_goes_to_last_worked_page(self):
        first_page = make_plan_page(self.project, label='First')
        second_page = make_plan_page(self.project, label='Second')
        Trace.objects.create(
            plan_page=second_page, tool_type=Trace.ToolType.COUNT, geometry=[{'x': 1, 'y': 1}],
        )
        Trace.objects.create(
            plan_page=first_page, tool_type=Trace.ToolType.COUNT, geometry=[{'x': 2, 'y': 2}],
        )
        # The most recent trace is on first_page, so takeoff resumes there,
        # even though second_page belongs to the newer plan.
        response = self.client.get(self._url())
        self.assertRedirects(response, reverse('plans:viewer', args=[first_page.pk]))

    def test_other_accounts_project_404s(self):
        foreign = Project.objects.create(account=self.other.account, name='B House')
        response = self.client.get(self._url(foreign))
        self.assertEqual(response.status_code, 404)

    def test_button_rendered_on_project_detail(self):
        response = self.client.get(reverse('projects:detail', args=[self.project.pk]))
        self.assertContains(response, self._url())
        self.assertContains(response, 'Start Takeoff')
