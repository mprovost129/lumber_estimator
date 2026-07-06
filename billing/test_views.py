from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.models import Estimate, Project

User = get_user_model()


class BillingOverviewViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='billing@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Billing House')
        self.estimate = Estimate.objects.create(project=self.project, name='Estimate 7')

    def test_requires_login(self):
        response = self.client.get(reverse('billing:overview'))
        self.assertEqual(response.status_code, 302)

    def test_renders_recent_estimates(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('billing:overview'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Billing')
        self.assertContains(response, 'Estimate 7')
        self.assertContains(response, 'Locked')
