import json
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from projects.models import JobSettings, Project

from .models import Trace
from .test_traces import make_plan_page

User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class WallElevationViewTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email='wall-a@example.com', password='testpass123')
        self.user_b = User.objects.create_user(email='wall-b@example.com', password='testpass123')
        self.project_a = Project.objects.create(account=self.user_a.account, name='Wall A House')
        self.project_b = Project.objects.create(account=self.user_b.account, name='Wall B House')
        JobSettings.objects.create(project=self.project_a)
        JobSettings.objects.create(project=self.project_b)
        self.page_a = make_plan_page(self.project_a)
        self.page_b = make_plan_page(self.project_b)
        self.page_a.scale_pixels_per_foot = Decimal('10')
        self.page_a.save(update_fields=['scale_pixels_per_foot'])

    def _create_wall(self, page, tool_type=Trace.ToolType.LINE, **extra_settings):
        settings = {'stud_spacing_in': 16, 'wall_height_in': 96}
        settings.update(extra_settings)
        return Trace.objects.create(
            plan_page=page, tool_type=tool_type,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}], settings=settings,
        )

    def test_returns_generated_model_for_owner(self):
        wall = self._create_wall(self.page_a)
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('plans:wall-elevation', args=[wall.pk]))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['trace_id'], wall.pk)
        self.assertIn('members', body)
        self.assertIn('cut_list', body)

    def test_requires_login(self):
        wall = self._create_wall(self.page_a)
        response = self.client.get(reverse('plans:wall-elevation', args=[wall.pk]))
        self.assertEqual(response.status_code, 302)

    def test_404s_for_other_accounts_trace(self):
        wall = self._create_wall(self.page_b)
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('plans:wall-elevation', args=[wall.pk]))

        self.assertEqual(response.status_code, 404)

    def test_400s_when_page_is_not_calibrated(self):
        wall = self._create_wall(self.page_b)  # page_b has no scale set
        self.client.force_login(self.user_b)

        response = self.client.get(reverse('plans:wall-elevation', args=[wall.pk]))

        self.assertEqual(response.status_code, 400)
        self.assertIn('Calibrate', response.json()['error'])

    def test_400s_for_non_wall_tool_type(self):
        count_trace = Trace.objects.create(
            plan_page=self.page_a, tool_type=Trace.ToolType.COUNT,
            geometry=[{'x': 0, 'y': 0}],
        )
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('plans:wall-elevation', args=[count_trace.pk]))

        self.assertEqual(response.status_code, 400)

    def test_polyline_wall_is_supported(self):
        wall = self._create_wall(self.page_a, tool_type=Trace.ToolType.POLYLINE)
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('plans:wall-elevation', args=[wall.pk]))

        self.assertEqual(response.status_code, 200)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TraceUpdateWallOverrideTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='override@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Override House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.page.scale_pixels_per_foot = Decimal('10')
        self.page.save(update_fields=['scale_pixels_per_foot'])
        self.wall = Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
            settings={'stud_spacing_in': 16, 'wall_height_in': 96},
        )
        self.client.force_login(self.user)

    def test_valid_overrides_are_persisted(self):
        settings = {
            'stud_spacing_in': 16, 'wall_height_in': 96,
            'wall_member_overrides': {'deleted': ['stud_1']},
        }
        response = self.client.post(
            reverse('plans:trace-update', args=[self.wall.pk]),
            data=json.dumps({'settings': settings}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.wall.refresh_from_db()
        self.assertEqual(self.wall.settings['wall_member_overrides']['deleted'], ['stud_1'])

    def test_malformed_overrides_are_rejected_with_400(self):
        settings = {
            'stud_spacing_in': 16, 'wall_height_in': 96,
            'wall_member_overrides': {'deleted': 'not-a-list'},
        }
        response = self.client.post(
            reverse('plans:trace-update', args=[self.wall.pk]),
            data=json.dumps({'settings': settings}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        # The trace must be untouched - a rejected update shouldn't partially save.
        self.wall.refresh_from_db()
        self.assertNotIn('wall_member_overrides', self.wall.settings)

    def test_malformed_overrides_rejected_on_create_too(self):
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'line', 'geometry': [{'x': 0, 'y': 0}, {'x': 50, 'y': 0}],
                'settings': {'wall_member_overrides': {'added': 'not-a-list'}},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
