import json
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import MaterialProduct
from estimating.models import Assembly
from projects.models import JobSettings, Project

from .models import Trace
from .test_traces import make_plan_page

User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TraceBatchEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='batch@example.com', password='testpass123')
        self.other = User.objects.create_user(email='batch-other@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Batch House')
        self.other_project = Project.objects.create(account=self.other.account, name='Other Batch House')
        JobSettings.objects.create(project=self.project)
        JobSettings.objects.create(project=self.other_project)
        self.page = make_plan_page(self.project)
        self.page.scale_pixels_per_foot = 10
        self.page.save(update_fields=['scale_pixels_per_foot'])
        self.other_page = make_plan_page(self.other_project)
        self.material_a = MaterialProduct.objects.create(name='Batch A', input_type=MaterialProduct.InputType.FT)
        self.material_b = MaterialProduct.objects.create(name='Batch B', input_type=MaterialProduct.InputType.FT)
        self.line_assembly = Assembly.objects.create(name='Batch Line Assembly', tool_type='line')
        self.count_assembly = Assembly.objects.create(name='Batch Count Assembly', tool_type='count')
        self.line_1 = Trace.objects.create(
            plan_page=self.page, tool_type='line',
            geometry=[{'x': 0, 'y': 0}, {'x': 10, 'y': 0}],
            material=self.material_a, color='#111111', settings={'stud_spacing_in': 16},
        )
        self.line_2 = Trace.objects.create(
            plan_page=self.page, tool_type='line',
            geometry=[{'x': 0, 'y': 10}, {'x': 10, 'y': 10}],
            material=self.material_a, color='#222222', settings={'stud_spacing_in': 16},
        )
        self.count_trace = Trace.objects.create(
            plan_page=self.page, tool_type='count',
            geometry=[{'x': 5, 'y': 5}],
            material=self.material_a, color='#333333', settings={},
        )
        self.foreign_trace = Trace.objects.create(
            plan_page=self.other_page, tool_type='line',
            geometry=[{'x': 0, 'y': 0}, {'x': 5, 'y': 0}],
        )
        self.batch_update_url = reverse('plans:trace-batch-update')
        self.batch_delete_url = reverse('plans:trace-batch-delete')
        self.client.force_login(self.user)

    def test_batch_update_can_apply_material_and_color_to_mixed_types(self):
        response = self.client.post(
            self.batch_update_url,
            data=json.dumps({
                'trace_ids': [self.line_1.pk, self.count_trace.pk],
                'apply_material': True,
                'material_id': self.material_b.pk,
                'apply_color': True,
                'color': '#ABCDEF',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.line_1.refresh_from_db()
        self.count_trace.refresh_from_db()
        self.assertEqual(self.line_1.material_id, self.material_b.pk)
        self.assertEqual(self.count_trace.material_id, self.material_b.pk)
        self.assertEqual(self.line_1.color, '#ABCDEF')
        self.assertEqual(self.count_trace.color, '#ABCDEF')

    def test_batch_update_rejects_assembly_for_mixed_types(self):
        response = self.client.post(
            self.batch_update_url,
            data=json.dumps({
                'trace_ids': [self.line_1.pk, self.count_trace.pk],
                'apply_assembly': True,
                'assembly_id': self.line_assembly.pk,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.line_1.refresh_from_db()
        self.count_trace.refresh_from_db()
        self.assertIsNone(self.line_1.assembly_id)
        self.assertIsNone(self.count_trace.assembly_id)

    def test_batch_update_can_apply_same_type_assembly_and_settings(self):
        response = self.client.post(
            self.batch_update_url,
            data=json.dumps({
                'trace_ids': [self.line_1.pk, self.line_2.pk],
                'apply_assembly': True,
                'assembly_id': self.line_assembly.pk,
                'apply_settings': True,
                'settings': {'stud_spacing_in': 24, 'wall_height_in': 97.125},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.line_1.refresh_from_db()
        self.line_2.refresh_from_db()
        self.assertEqual(self.line_1.assembly_id, self.line_assembly.pk)
        self.assertEqual(self.line_2.assembly_id, self.line_assembly.pk)
        self.assertEqual(self.line_1.settings['stud_spacing_in'], 24)
        self.assertEqual(self.line_2.settings['wall_height_in'], 97.125)

    def test_batch_delete_removes_multiple_traces(self):
        response = self.client.post(
            self.batch_delete_url,
            data=json.dumps({'trace_ids': [self.line_1.pk, self.line_2.pk]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Trace.objects.filter(pk=self.line_1.pk).exists())
        self.assertFalse(Trace.objects.filter(pk=self.line_2.pk).exists())
        self.assertTrue(Trace.objects.filter(pk=self.count_trace.pk).exists())
        self.assertEqual(response.json()['count'], 2)

    def test_batch_delete_cannot_touch_foreign_trace(self):
        response = self.client.post(
            self.batch_delete_url,
            data=json.dumps({'trace_ids': [self.line_1.pk, self.foreign_trace.pk]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Trace.objects.filter(pk=self.line_1.pk).exists())
        self.assertTrue(Trace.objects.filter(pk=self.foreign_trace.pk).exists())
