from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import JobSettings, Project, ProjectTemplate

User = get_user_model()


class ProjectTemplateLibraryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='template-test@example.com', password='testpass123')
        self.other = User.objects.create_user(email='other-template@example.com', password='testpass123')
        self.client.force_login(self.user)

    def test_library_shows_seeded_starters(self):
        response = self.client.get(reverse('projects:template-library'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1-Story Ranch, 9 ft 1-1/8 in')
        self.assertContains(response, 'Colonial, 9 ft 1-1/8 in First, 8 ft 1-1/8 in Second')

    def test_can_create_custom_template(self):
        response = self.client.post(reverse('projects:template-create'), data={
            'name': '2-Story Walkout',
            'description': 'Saved defaults for a common house type.',
            'num_floors': 2,
            'foundation_type': JobSettings.FoundationType.CRAWL_SPACE,
            'first_floor_wall_height_in': '109.125',
            'second_floor_wall_height_in': '97.125',
            'stud_spacing_in': 16,
            'roof_framing': JobSettings.RoofFraming.TRUSSES,
            'roof_pitch_rise_per_12': 8,
            'floor_material': 'I-joists',
            'siding_material': 'Vinyl siding',
        })

        self.assertEqual(response.status_code, 302)
        template = ProjectTemplate.objects.get(account=self.user.account, name='2-Story Walkout')
        self.assertEqual(template.first_floor_wall_height_in, Decimal('109.125'))
        self.assertEqual(template.second_floor_wall_height_in, Decimal('97.125'))

    def test_can_update_custom_template(self):
        template = ProjectTemplate.objects.create(
            account=self.user.account,
            name='Editable Template',
            num_floors=1,
            first_floor_wall_height_in=Decimal('97.125'),
        )

        response = self.client.post(reverse('projects:template-update', args=[template.pk]), data={
            'name': 'Editable Template',
            'description': 'Updated',
            'num_floors': 1,
            'foundation_type': JobSettings.FoundationType.SLAB,
            'first_floor_wall_height_in': '109.125',
            'stud_spacing_in': 16,
            'roof_framing': JobSettings.RoofFraming.TRUSSES,
            'roof_pitch_rise_per_12': '',
            'floor_material': '',
            'siding_material': '',
            'basement_wall_height_in': '',
            'second_floor_wall_height_in': '',
        })

        self.assertEqual(response.status_code, 302)
        template.refresh_from_db()
        self.assertEqual(template.description, 'Updated')
        self.assertEqual(template.first_floor_wall_height_in, Decimal('109.125'))

    def test_cannot_edit_other_accounts_template(self):
        template = ProjectTemplate.objects.create(
            account=self.other.account,
            name='Foreign Template',
            num_floors=1,
            first_floor_wall_height_in=Decimal('97.125'),
        )

        response = self.client.get(reverse('projects:template-update', args=[template.pk]))

        self.assertEqual(response.status_code, 404)

    def test_save_project_settings_as_template_prefills_form(self):
        project = Project.objects.create(account=self.user.account, name='Saved House')
        JobSettings.objects.create(
            project=project,
            num_floors=2,
            foundation_type=JobSettings.FoundationType.SLAB,
            first_floor_wall_height_in=Decimal('109.125'),
            second_floor_wall_height_in=Decimal('97.125'),
            stud_spacing_in=16,
            roof_framing=JobSettings.RoofFraming.TRUSSES,
        )

        response = self.client.get(f"{reverse('projects:template-create')}?source_project={project.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Saved House Template')
        self.assertContains(response, '109.125')
        self.assertContains(response, '97.125')
