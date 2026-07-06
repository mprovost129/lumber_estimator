import importlib
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

# The migration module's name starts with a digit, so it can't be imported with
# a normal `from plans.migrations.0006_... import ...` statement.
_backfill_module = importlib.import_module('plans.migrations.0006_backfill_opening_parent_wall')
backfill_parent_wall = _backfill_module.backfill_parent_wall


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ParentWallResolutionTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email='parent-a@example.com', password='testpass123')
        self.user_b = User.objects.create_user(email='parent-b@example.com', password='testpass123')
        self.project_a = Project.objects.create(account=self.user_a.account, name='Parent A House')
        self.project_b = Project.objects.create(account=self.user_b.account, name='Parent B House')
        JobSettings.objects.create(project=self.project_a)
        JobSettings.objects.create(project=self.project_b)
        self.page_a = make_plan_page(self.project_a)
        self.page_b = make_plan_page(self.project_b)
        self.page_a.scale_pixels_per_foot = Decimal('10')
        self.page_a.save(update_fields=['scale_pixels_per_foot'])

        self.wall = Trace.objects.create(
            plan_page=self.page_a, tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
        )
        self.client.force_login(self.user_a)

    def test_attach_opening_to_wall_persists_and_round_trips(self):
        opening = Trace.objects.create(
            plan_page=self.page_a, tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 40, 'y': 0}, {'x': 60, 'y': 0}],
        )
        response = self.client.post(
            reverse('plans:trace-update', args=[opening.pk]),
            data=json.dumps({'parent_wall_id': self.wall.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['parent_wall_id'], self.wall.pk)
        opening.refresh_from_db()
        self.assertEqual(opening.parent_wall_id, self.wall.pk)

    def test_non_opening_trace_cannot_set_parent_wall(self):
        other_wall = Trace.objects.create(
            plan_page=self.page_a, tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 50}, {'x': 100, 'y': 50}],
        )
        response = self.client.post(
            reverse('plans:trace-update', args=[other_wall.pk]),
            data=json.dumps({'parent_wall_id': self.wall.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_parent_wall_must_be_line_or_polyline(self):
        opening = Trace.objects.create(
            plan_page=self.page_a, tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 40, 'y': 0}, {'x': 60, 'y': 0}],
        )
        not_a_wall = Trace.objects.create(
            plan_page=self.page_a, tool_type=Trace.ToolType.COUNT,
            geometry=[{'x': 10, 'y': 10}],
        )
        response = self.client.post(
            reverse('plans:trace-update', args=[opening.pk]),
            data=json.dumps({'parent_wall_id': not_a_wall.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_parent_wall_must_be_on_the_same_page(self):
        other_page = make_plan_page(self.project_a, label='Second Page')
        opening = Trace.objects.create(
            plan_page=self.page_a, tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 40, 'y': 0}, {'x': 60, 'y': 0}],
        )
        wall_on_other_page = Trace.objects.create(
            plan_page=other_page, tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
        )
        response = self.client.post(
            reverse('plans:trace-update', args=[opening.pk]),
            data=json.dumps({'parent_wall_id': wall_on_other_page.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_attach_to_other_accounts_wall(self):
        other_wall = Trace.objects.create(
            plan_page=self.page_b, tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
        )
        opening = Trace.objects.create(
            plan_page=self.page_a, tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 40, 'y': 0}, {'x': 60, 'y': 0}],
        )
        response = self.client.post(
            reverse('plans:trace-update', args=[opening.pk]),
            data=json.dumps({'parent_wall_id': other_wall.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_can_set_parent_wall_at_creation(self):
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page_a.pk]),
            data=json.dumps({
                'tool_type': 'opening', 'geometry': [{'x': 40, 'y': 0}, {'x': 60, 'y': 0}],
                'parent_wall_id': self.wall.pk,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['parent_wall_id'], self.wall.pk)

    def test_deleting_wall_unattaches_opening_instead_of_deleting_it(self):
        opening = Trace.objects.create(
            plan_page=self.page_a, tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 40, 'y': 0}, {'x': 60, 'y': 0}], parent_wall=self.wall,
        )
        self.wall.delete()
        opening.refresh_from_db()
        self.assertIsNone(opening.parent_wall_id)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ParentWallBackfillMigrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='backfill@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Backfill House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.page.scale_pixels_per_foot = Decimal('10')
        self.page.save(update_fields=['scale_pixels_per_foot'])

    def test_backfill_attaches_nearby_opening_to_the_closest_wall(self):
        near_wall = Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
        )
        far_wall = Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 500}, {'x': 100, 'y': 500}],
        )
        opening = Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 40, 'y': 1}, {'x': 60, 'y': 1}],
        )

        class FakeApps:
            def get_model(self, app_label, model_name):
                return Trace

        backfill_parent_wall(FakeApps(), None)

        opening.refresh_from_db()
        self.assertEqual(opening.parent_wall_id, near_wall.pk)
        self.assertNotEqual(opening.parent_wall_id, far_wall.pk)

    def test_backfill_leaves_opening_unattached_when_nothing_is_close_enough(self):
        Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
        )
        opening = Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 40, 'y': 500}, {'x': 60, 'y': 500}],
        )

        class FakeApps:
            def get_model(self, app_label, model_name):
                return Trace

        backfill_parent_wall(FakeApps(), None)

        opening.refresh_from_db()
        self.assertIsNone(opening.parent_wall_id)
