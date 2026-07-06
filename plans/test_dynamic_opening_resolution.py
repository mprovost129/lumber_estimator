import json
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from estimating.models import Assembly, LineItem
from projects.models import JobSettings, Project

from .models import Trace
from .test_traces import make_plan_page
from .views import _peek_parent_wall, _resolve_opening_assembly

User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DynamicOpeningResolutionTests(TestCase):
    """A window/door attached to a classified wall should automatically get
    the matching Opening assembly - no manual pick required, and it can't
    drift out of sync with whichever wall it's actually attached to."""

    def setUp(self):
        self.user = User.objects.create_user(email='dynamic-opening@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Dynamic Opening House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.page.scale_pixels_per_foot = Decimal('10')
        self.page.save(update_fields=['scale_pixels_per_foot'])

        self.exterior_wall_assembly = Assembly.objects.get(
            name='2x6 Exterior Wall on Slab - 16 in OC', account__isnull=True,
        )
        self.bearing_wall_assembly = Assembly.objects.get(
            name='2x6 Interior Bearing Wall - 16 in OC', account__isnull=True,
        )
        self.legacy_wall_assembly = Assembly.objects.get(name='2x4 Wall - 16 in OC', account__isnull=True)
        self.legacy_opening_assembly = Assembly.objects.get(
            name='Window/Door Opening - 2x10 Header (2x6 Wall)', account__isnull=True,
        )

        self.exterior_wall = Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.LINE, assembly=self.exterior_wall_assembly,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
        )
        self.bearing_wall = Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.LINE, assembly=self.bearing_wall_assembly,
            geometry=[{'x': 0, 'y': 200}, {'x': 100, 'y': 200}],
        )
        self.legacy_wall = Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.LINE, assembly=self.legacy_wall_assembly,
            geometry=[{'x': 0, 'y': 400}, {'x': 100, 'y': 400}],
        )
        self.client.force_login(self.user)

    def _create_opening(self, opening_type, parent_wall_id=None, assembly_id=None, geometry=None):
        payload = {
            'tool_type': 'opening',
            'geometry': geometry or [{'x': 20, 'y': 0}, {'x': 40, 'y': 0}],
            'settings': {'opening_type': opening_type},
        }
        if parent_wall_id is not None:
            payload['parent_wall_id'] = parent_wall_id
        if assembly_id is not None:
            payload['assembly_id'] = assembly_id
        return self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps(payload), content_type='application/json',
        )

    def test_window_attached_to_exterior_wall_auto_resolves(self):
        response = self._create_opening('window', parent_wall_id=self.exterior_wall.pk)
        self.assertEqual(response.status_code, 201, response.content)
        trace = Trace.objects.get(pk=response.json()['id'])
        self.assertEqual(trace.assembly.name, 'Window Opening - Exterior Wall Header')

    def test_door_attached_to_bearing_wall_auto_resolves(self):
        response = self._create_opening('door', parent_wall_id=self.bearing_wall.pk)
        self.assertEqual(response.status_code, 201, response.content)
        trace = Trace.objects.get(pk=response.json()['id'])
        self.assertEqual(trace.assembly.name, 'Door Opening - Interior Bearing Wall Header')

    def test_explicit_assembly_id_is_ignored_when_auto_resolution_succeeds(self):
        # Client sends the legacy assembly explicitly, but a real match exists.
        response = self._create_opening(
            'window', parent_wall_id=self.exterior_wall.pk, assembly_id=self.legacy_opening_assembly.pk,
        )
        self.assertEqual(response.status_code, 201, response.content)
        trace = Trace.objects.get(pk=response.json()['id'])
        self.assertEqual(trace.assembly.name, 'Window Opening - Exterior Wall Header')

    def test_attaching_to_unclassified_legacy_wall_falls_back_to_manual_pick(self):
        response = self._create_opening(
            'window', parent_wall_id=self.legacy_wall.pk, assembly_id=self.legacy_opening_assembly.pk,
        )
        self.assertEqual(response.status_code, 201, response.content)
        trace = Trace.objects.get(pk=response.json()['id'])
        self.assertEqual(trace.assembly_id, self.legacy_opening_assembly.pk)

    def test_reattaching_to_a_different_wall_reresolves_the_assembly(self):
        create_response = self._create_opening('window', parent_wall_id=self.exterior_wall.pk)
        opening_id = create_response.json()['id']
        self.assertEqual(
            Trace.objects.get(pk=opening_id).assembly.name, 'Window Opening - Exterior Wall Header',
        )

        response = self.client.post(
            reverse('plans:trace-update', args=[opening_id]),
            data=json.dumps({
                'parent_wall_id': self.bearing_wall.pk, 'settings': {'opening_type': 'window'},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        trace = Trace.objects.get(pk=opening_id)
        self.assertEqual(trace.assembly.name, 'Window Opening - Interior Bearing Wall Header')

    def test_detaching_wall_with_no_new_assembly_clears_the_assembly(self):
        create_response = self._create_opening('window', parent_wall_id=self.exterior_wall.pk)
        opening_id = create_response.json()['id']
        self.assertIsNotNone(Trace.objects.get(pk=opening_id).assembly_id)

        response = self.client.post(
            reverse('plans:trace-update', args=[opening_id]),
            data=json.dumps({'parent_wall_id': None, 'settings': {'opening_type': 'window'}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        trace = Trace.objects.get(pk=opening_id)
        self.assertIsNone(trace.assembly_id)
        self.assertFalse(LineItem.objects.filter(trace=trace).exists())

    def test_invalid_parent_wall_id_still_produces_the_existing_error(self):
        response = self._create_opening('window', parent_wall_id=999999)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Invalid parent wall.')

    def test_uncalibrated_page_still_blocks_even_when_auto_resolution_would_succeed(self):
        self.page.scale_pixels_per_foot = None
        self.page.save(update_fields=['scale_pixels_per_foot'])
        response = self._create_opening('window', parent_wall_id=self.exterior_wall.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Calibrate this page before assigning an assembly.')
        self.assertFalse(Trace.objects.filter(tool_type=Trace.ToolType.OPENING).exists())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ResolverUnitTests(TestCase):
    """Direct tests of the pure resolver helpers, independent of the view layer."""

    def setUp(self):
        self.user = User.objects.create_user(email='resolver-unit@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Resolver Unit House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.page.scale_pixels_per_foot = Decimal('10')
        self.page.save(update_fields=['scale_pixels_per_foot'])
        self.exterior_wall_assembly = Assembly.objects.get(
            name='2x6 Exterior Wall on Slab - 16 in OC', account__isnull=True,
        )
        self.wall = Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.LINE, assembly=self.exterior_wall_assembly,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
        )

    def test_peek_parent_wall_returns_none_for_missing_id(self):
        self.assertIsNone(_peek_parent_wall(self.user.account, None, self.page))
        self.assertIsNone(_peek_parent_wall(self.user.account, 999999, self.page))

    def test_peek_parent_wall_finds_a_real_wall(self):
        found = _peek_parent_wall(self.user.account, self.wall.pk, self.page)
        self.assertEqual(found, self.wall)

    def test_resolve_opening_assembly_returns_none_without_a_wall(self):
        self.assertIsNone(_resolve_opening_assembly(self.user.account, {'opening_type': 'window'}, None))

    def test_resolve_opening_assembly_matches_window_to_exterior_wall(self):
        resolved = _resolve_opening_assembly(self.user.account, {'opening_type': 'window'}, self.wall)
        self.assertEqual(resolved.name, 'Window Opening - Exterior Wall Header')

    def test_resolve_opening_assembly_defaults_to_window_when_opening_type_missing(self):
        resolved = _resolve_opening_assembly(self.user.account, {}, self.wall)
        self.assertEqual(resolved.name, 'Window Opening - Exterior Wall Header')
