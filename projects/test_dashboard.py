from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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
