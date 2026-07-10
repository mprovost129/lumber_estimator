import json
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import MaterialProduct
from estimating.models import Assembly, LoadType
from projects.models import JobSettings, Project

from .models import Plan, PlanPage, Trace

User = get_user_model()


def make_plan_page(project, label='Test Page'):
    plan = Plan.objects.create(project=project, name='Test Plan')
    page = PlanPage(plan=plan, page_number=1, label=label)
    page.image.save('page.png', SimpleUploadedFile('page.png', b'fake-image-bytes'), save=False)
    page.thumbnail.save('thumb.png', SimpleUploadedFile('thumb.png', b'fake-thumb-bytes'), save=False)
    page.save()
    return page


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TraceTenancyTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email='a@example.com', password='testpass123')
        self.user_b = User.objects.create_user(email='b@example.com', password='testpass123')
        self.project_a = Project.objects.create(account=self.user_a.account, name='A House')
        self.project_b = Project.objects.create(account=self.user_b.account, name='B House')
        JobSettings.objects.create(project=self.project_a)
        JobSettings.objects.create(project=self.project_b)
        self.page_a = make_plan_page(self.project_a)
        self.page_b = make_plan_page(self.project_b)

    def test_viewer_404s_for_other_accounts_page(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('plans:viewer', args=[self.page_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_viewer_context_includes_estimate_and_material_summary_url(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('plans:viewer', args=[self.page_a.pk]))
        self.assertEqual(response.status_code, 200)
        estimate = self.project_a.get_or_create_estimate()
        self.assertEqual(response.context['estimate'], estimate)
        self.assertContains(
            response, reverse('estimating:estimate-material-summary', args=[estimate.pk]),
        )
        self.assertContains(response, 'data-keep-tool-active-after-draw="true"')

    def test_viewer_assemblies_data_carries_is_default_flag(self):
        # The viewer auto-selects a default assembly per semantic tool, which
        # needs is_default present on each assembly in the serialized payload.
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('plans:viewer', args=[self.page_a.pk]))
        assemblies = response.context['assemblies_data']
        self.assertTrue(assemblies, 'expected seeded global assemblies in the viewer payload')
        self.assertTrue(all('is_default' in assembly for assembly in assemblies))
        self.assertTrue(any(assembly['is_default'] for assembly in assemblies))

    def test_viewer_context_includes_load_types_data(self):
        LoadType.objects.create(account=self.user_a.account, name='First Floor System', display_order=1)
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('plans:viewer', args=[self.page_a.pk]))
        load_types = response.context['load_types_data']
        self.assertTrue(any(load_type['name'] == 'First Floor System' for load_type in load_types))

    def test_viewer_page_strip_lists_all_project_pages_but_not_foreign_ones(self):
        # The strip spans every page in the project, across plans, oldest plan
        # first, and never leaks another account's pages.
        second_page = make_plan_page(self.project_a, label='Second Floor')
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('plans:viewer', args=[self.page_a.pk]))
        strip_ids = [p.pk for p in response.context['project_pages']]
        self.assertEqual(strip_ids, [self.page_a.pk, second_page.pk])
        self.assertNotIn(self.page_b.pk, strip_ids)
        self.assertContains(response, 'id="page-strip"')
        self.assertContains(response, reverse('plans:viewer', args=[second_page.pk]))
        # The current page is highlighted.
        self.assertContains(response, 'page-strip-item is-current')

    def test_viewer_page_strip_hidden_for_single_page_project(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('plans:viewer', args=[self.page_a.pk]))
        self.assertNotContains(response, 'id="page-strip"')

    def test_cannot_create_trace_on_other_accounts_page(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page_b.pk]),
            data=json.dumps({'tool_type': 'line', 'geometry': [{'x': 0, 'y': 0}, {'x': 10, 'y': 10}]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_assign_other_accounts_private_material(self):
        private_material = MaterialProduct.objects.create(
            account=self.user_b.account, name='B Only Material', input_type=MaterialProduct.InputType.FT,
        )
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page_a.pk]),
            data=json.dumps({
                'tool_type': 'line', 'geometry': [{'x': 0, 'y': 0}, {'x': 10, 'y': 10}],
                'material_id': private_material.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_delete_other_accounts_trace(self):
        trace = Trace.objects.create(
            plan_page=self.page_b, tool_type='line',
            geometry=[{'x': 0, 'y': 0}, {'x': 1, 'y': 1}],
        )
        self.client.force_login(self.user_a)
        response = self.client.post(reverse('plans:trace-delete', args=[trace.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Trace.objects.filter(pk=trace.pk).exists())

    def test_cannot_update_other_accounts_trace(self):
        trace = Trace.objects.create(
            plan_page=self.page_b, tool_type='line',
            geometry=[{'x': 0, 'y': 0}, {'x': 1, 'y': 1}],
        )
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:trace-update', args=[trace.pk]),
            data=json.dumps({'settings': {'stud_spacing_in': 24}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_update_trace_with_other_accounts_private_material(self):
        trace = Trace.objects.create(
            plan_page=self.page_a, tool_type='line',
            geometry=[{'x': 0, 'y': 0}, {'x': 1, 'y': 1}],
        )
        private_material = MaterialProduct.objects.create(
            account=self.user_b.account, name='B Only Material 2', input_type=MaterialProduct.InputType.FT,
        )
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:trace-update', args=[trace.pk]),
            data=json.dumps({'material_id': private_material.id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TraceUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='edit@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Edit House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.material_2x4 = MaterialProduct.objects.create(name='2x4 Edit', input_type=MaterialProduct.InputType.FT)
        self.material_2x6 = MaterialProduct.objects.create(name='2x6 Edit', input_type=MaterialProduct.InputType.FT)
        self.trace = Trace.objects.create(
            plan_page=self.page, tool_type='line',
            geometry=[{'x': 0, 'y': 0}, {'x': 10, 'y': 0}],
            material=self.material_2x4, settings={'stud_spacing_in': 16},
        )

    def test_update_changes_material_and_settings_without_touching_geometry(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('plans:trace-update', args=[self.trace.pk]),
            data=json.dumps({'material_id': self.material_2x6.id, 'settings': {'stud_spacing_in': 24}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        self.trace.refresh_from_db()
        self.assertEqual(self.trace.material_id, self.material_2x6.id)
        self.assertEqual(self.trace.settings['stud_spacing_in'], 24)
        self.assertEqual(self.trace.geometry, [{'x': 0, 'y': 0}, {'x': 10, 'y': 0}])
        self.assertEqual(self.trace.tool_type, 'line')

    def test_update_can_clear_material(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse('plans:trace-update', args=[self.trace.pk]),
            data=json.dumps({'material_id': None, 'settings': {}}),
            content_type='application/json',
        )
        self.trace.refresh_from_db()
        self.assertIsNone(self.trace.material_id)

    def test_update_can_set_load_type(self):
        load_type = LoadType.objects.create(account=self.user.account, name='Roof System', display_order=1)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('plans:trace-update', args=[self.trace.pk]),
            data=json.dumps({
                'material_id': self.material_2x4.id,
                'load_type_id': load_type.pk,
                'color': '',
                'settings': {'stud_spacing_in': 16},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.trace.refresh_from_db()
        self.assertEqual(self.trace.load_type_id, load_type.pk)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TraceSnapshotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='snap@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Snap House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.material_2x4 = MaterialProduct.objects.create(name='2x4 Test', input_type=MaterialProduct.InputType.FT)
        self.material_2x6 = MaterialProduct.objects.create(name='2x6 Test', input_type=MaterialProduct.InputType.FT)

    def test_changing_settings_does_not_mutate_earlier_trace(self):
        self.client.force_login(self.user)
        create_url = reverse('plans:trace-create', args=[self.page.pk])

        first = self.client.post(create_url, data=json.dumps({
            'tool_type': 'line', 'geometry': [{'x': 0, 'y': 0}, {'x': 10, 'y': 0}],
            'material_id': self.material_2x4.id, 'settings': {'stud_spacing_in': 16},
        }), content_type='application/json').json()

        second = self.client.post(create_url, data=json.dumps({
            'tool_type': 'line', 'geometry': [{'x': 0, 'y': 10}, {'x': 10, 'y': 10}],
            'material_id': self.material_2x6.id, 'settings': {'stud_spacing_in': 24},
        }), content_type='application/json').json()

        first_trace = Trace.objects.get(pk=first['id'])
        second_trace = Trace.objects.get(pk=second['id'])
        self.assertEqual(first_trace.material_id, self.material_2x4.id)
        self.assertEqual(first_trace.settings['stud_spacing_in'], 16)
        self.assertEqual(second_trace.material_id, self.material_2x6.id)
        self.assertEqual(second_trace.settings['stud_spacing_in'], 24)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PolylineTraceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='polyline@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Shape House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.page.scale_pixels_per_foot = 10
        self.page.save(update_fields=['scale_pixels_per_foot'])
        self.client.force_login(self.user)

    def test_create_closed_polyline_with_custom_color(self):
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'polyline',
                'geometry': [
                    {'x': 0, 'y': 0}, {'x': 100, 'y': 0},
                    {'x': 100, 'y': 50}, {'x': 0, 'y': 50},
                ],
                'settings': {'closed': True},
                'color': '#123ABC',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['measurement_display'], '50 sq ft')
        trace = Trace.objects.get(pk=response.json()['id'])
        self.assertEqual(trace.tool_type, Trace.ToolType.POLYLINE)
        self.assertEqual(trace.color, '#123ABC')
        self.assertTrue(trace.settings['closed'])

    def test_closed_polyline_requires_three_points(self):
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'polyline',
                'geometry': [{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
                'settings': {'closed': True},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_color(self):
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'polyline',
                'geometry': [{'x': 0, 'y': 0}, {'x': 100, 'y': 0}],
                'color': 'red',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_closed_polyline_can_use_area_assembly(self):
        assembly = Assembly.objects.create(name='Shape Area', tool_type='area')
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'polyline',
                'geometry': [
                    {'x': 0, 'y': 0}, {'x': 100, 'y': 0},
                    {'x': 100, 'y': 50}, {'x': 0, 'y': 50},
                ],
                'settings': {'closed': True},
                'assembly_id': assembly.pk,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Trace.objects.get(pk=response.json()['id']).assembly, assembly)
