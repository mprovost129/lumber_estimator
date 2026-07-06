from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import JobSettings, Project, ProjectTemplate

User = get_user_model()


class ProjectSetupWizardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='wizard-test@example.com', password='testpass123')
        self.client.force_login(self.user)

    def _submit(self, **overrides):
        data = {
            'name': 'Wizard House', 'client': 'Wizard Client',
            'num_floors': 1, 'foundation_type': JobSettings.FoundationType.SLAB,
            'first_floor_wall_height_in': '109.125',
            'stud_spacing_in': 16, 'roof_framing': JobSettings.RoofFraming.TRUSSES,
        }
        data.update(overrides)
        return self.client.post(reverse('projects:create'), data=data)

    def test_wizard_saves_roof_pitch_and_siding(self):
        response = self._submit(roof_pitch_rise_per_12=6, siding_material='Vinyl siding')
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(name='Wizard House')
        job_settings = JobSettings.objects.get(project=project)
        self.assertEqual(job_settings.roof_pitch_rise_per_12, 6)
        self.assertEqual(job_settings.siding_material, 'Vinyl siding')
        self.assertEqual(job_settings.first_floor_wall_height_in, Decimal('109.125'))

    def test_roof_pitch_and_siding_are_optional(self):
        response = self._submit()
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(name='Wizard House')
        job_settings = JobSettings.objects.get(project=project)
        self.assertIsNone(job_settings.roof_pitch_rise_per_12)
        self.assertEqual(job_settings.siding_material, '')

    def test_full_basement_requires_basement_wall_height(self):
        response = self._submit(foundation_type=JobSettings.FoundationType.FULL_BASEMENT)
        self.assertEqual(response.status_code, 200)  # re-rendered with a validation error
        self.assertContains(response, 'Required for a full basement foundation.')

    def test_full_basement_with_wall_height_succeeds(self):
        response = self._submit(
            foundation_type=JobSettings.FoundationType.FULL_BASEMENT, basement_wall_height_in='96',
        )
        self.assertEqual(response.status_code, 302)
        job_settings = JobSettings.objects.get(project__name='Wizard House')
        self.assertEqual(job_settings.foundation_type, JobSettings.FoundationType.FULL_BASEMENT)
        self.assertEqual(job_settings.basement_wall_height_in, Decimal('96'))

    def test_create_page_lists_project_templates(self):
        ProjectTemplate.objects.create(
            account=self.user.account,
            name='My Custom Colonial',
            num_floors=2,
            first_floor_wall_height_in=Decimal('109.125'),
            second_floor_wall_height_in=Decimal('97.125'),
        )

        response = self.client.get(reverse('projects:create'))

        self.assertContains(response, 'Start From a Template')
        self.assertContains(response, 'My Custom Colonial')
