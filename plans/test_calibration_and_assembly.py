import json
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Account
from catalog.models import MaterialLength, MaterialProduct
from estimating.models import Assembly, CalculationRule, LineItem
from projects.models import Estimate, JobSettings, Project

from .models import Trace
from .test_traces import make_plan_page

User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PlanPageCalibrateTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email='calib-a@example.com', password='testpass123')
        self.user_b = User.objects.create_user(email='calib-b@example.com', password='testpass123')
        self.project_a = Project.objects.create(account=self.user_a.account, name='Calib A House')
        self.project_b = Project.objects.create(account=self.user_b.account, name='Calib B House')
        JobSettings.objects.create(project=self.project_a)
        JobSettings.objects.create(project=self.project_b)
        self.page_a = make_plan_page(self.project_a)
        self.page_b = make_plan_page(self.project_b)

    def test_calibrate_sets_scale_from_known_length(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:page-calibrate', args=[self.page_a.pk]),
            data=json.dumps({'geometry': [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}], 'known_length_ft': 10}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.page_a.refresh_from_db()
        self.assertEqual(self.page_a.scale_pixels_per_foot, Decimal('30'))

    def test_calibrate_rejects_non_positive_length(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:page-calibrate', args=[self.page_a.pk]),
            data=json.dumps({'geometry': [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}], 'known_length_ft': 0}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_calibrate_other_accounts_page(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:page-calibrate', args=[self.page_b.pk]),
            data=json.dumps({'geometry': [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}], 'known_length_ft': 10}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_calibrate_from_preset_scale_sets_pixels_per_foot(self):
        # 1/4" = 1'-0" at the app's fixed 144 DPI (RENDER_ZOOM=2.0 * 72pt/in) -> 36 px/ft.
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:page-calibrate', args=[self.page_a.pk]),
            data=json.dumps({'scale_inches_per_foot': 0.25}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.page_a.refresh_from_db()
        self.assertEqual(self.page_a.scale_pixels_per_foot, Decimal('36'))

    def test_calibrate_from_preset_scale_ignores_geometry(self):
        # A preset scale is self-sufficient - no drawn line is needed, and any
        # geometry sent alongside it (there shouldn't be any from the real UI) must not matter.
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:page-calibrate', args=[self.page_a.pk]),
            data=json.dumps({'scale_inches_per_foot': 0.5, 'geometry': [{'x': 0, 'y': 0}]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.page_a.refresh_from_db()
        self.assertEqual(self.page_a.scale_pixels_per_foot, Decimal('72'))

    def test_calibrate_from_preset_scale_rejects_non_positive(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:page-calibrate', args=[self.page_a.pk]),
            data=json.dumps({'scale_inches_per_foot': 0}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_calibrate_from_preset_scale_rejects_non_numeric(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:page-calibrate', args=[self.page_a.pk]),
            data=json.dumps({'scale_inches_per_foot': 'not-a-number'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_calibrate_other_accounts_page_via_preset_scale(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse('plans:page-calibrate', args=[self.page_b.pk]),
            data=json.dumps({'scale_inches_per_foot': 0.25}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TraceAssemblyWiringTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='wire@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Wire House')
        JobSettings.objects.create(project=self.project)
        self.estimate = Estimate.objects.create(project=self.project)
        self.page = make_plan_page(self.project)

        self.stud = MaterialProduct.objects.create(name='Wire 2x6', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=self.stud, length_ft=16, is_default=True)

        self.assembly = Assembly.objects.create(name='Wire Test Wall', tool_type='line')
        CalculationRule.objects.create(
            assembly=self.assembly, material=self.stud, role='Stud',
            formula_kind=CalculationRule.FormulaKind.PER_SPACING, extra=1,
            waste_factor=Decimal('0'), order=1,
        )

        # 300px line = 10ft, so 30 pixels per foot.
        self.page.scale_pixels_per_foot = Decimal('30')
        self.page.save(update_fields=['scale_pixels_per_foot'])

    def test_create_trace_with_assembly_generates_line_items(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'line', 'geometry': [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}],
                'assembly_id': self.assembly.id, 'settings': {'stud_spacing_in': 16},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)

        trace = Trace.objects.get(pk=response.json()['id'])
        line_items = LineItem.objects.filter(trace=trace)
        self.assertEqual(line_items.count(), 1)
        # 10ft wall @ 16" OC: ceil(120/16)+1 = 8+1 = 9
        self.assertEqual(line_items.first().quantity, 9)

    def test_material_summary_reflects_newly_created_trace_line_items(self):
        # Exercises the same endpoint the plan viewer's live material list
        # panel polls after every trace create/update/delete.
        self.client.force_login(self.user)
        summary_url = reverse('estimating:estimate-material-summary', args=[self.estimate.pk])
        self.assertContains(self.client.get(summary_url), 'No materials yet')

        create_response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'line', 'geometry': [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}],
                'assembly_id': self.assembly.id, 'settings': {'stud_spacing_in': 16},
            }),
            content_type='application/json',
        )
        trace_id = create_response.json()['id']
        response = self.client.get(summary_url)
        self.assertContains(response, 'Wire 2x6')
        self.assertContains(response, '9')
        self.assertContains(response, f'data-trace-ids="{trace_id}"')

    def test_create_trace_with_assembly_requires_calibration(self):
        self.page.scale_pixels_per_foot = None
        self.page.save(update_fields=['scale_pixels_per_foot'])

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'line', 'geometry': [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}],
                'assembly_id': self.assembly.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Trace.objects.exists())

    def test_cannot_assign_other_accounts_private_assembly(self):
        other_account = Account.objects.create(name='Other Account')
        private_assembly = Assembly.objects.create(account=other_account, name='Private Wall', tool_type='line')

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'line', 'geometry': [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}],
                'assembly_id': private_assembly.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_updating_trace_to_add_assembly_generates_line_items(self):
        trace = Trace.objects.create(
            plan_page=self.page, tool_type='line', geometry=[{'x': 0, 'y': 0}, {'x': 300, 'y': 0}],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('plans:trace-update', args=[trace.pk]),
            data=json.dumps({'assembly_id': self.assembly.id, 'settings': {'stud_spacing_in': 16}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LineItem.objects.filter(trace=trace).count(), 1)

    def test_updating_trace_to_remove_assembly_clears_line_items(self):
        trace = Trace.objects.create(
            plan_page=self.page, tool_type='line', geometry=[{'x': 0, 'y': 0}, {'x': 300, 'y': 0}],
            assembly=self.assembly, settings={'stud_spacing_in': 16},
        )
        LineItem.objects.create(
            estimate=self.estimate, trace=trace, material=self.stud, role='Stud',
            quantity=9, source=LineItem.Source.TOOL,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('plans:trace-update', args=[trace.pk]),
            data=json.dumps({'assembly_id': None, 'settings': {}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LineItem.objects.filter(trace=trace).count(), 0)

    def test_regenerating_trace_replaces_its_own_line_items_only(self):
        create_url = reverse('plans:trace-create', args=[self.page.pk])
        update_url_base = 'plans:trace-update'
        self.client.force_login(self.user)

        response = self.client.post(create_url, data=json.dumps({
            'tool_type': 'line', 'geometry': [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}],
            'assembly_id': self.assembly.id, 'settings': {'stud_spacing_in': 16},
        }), content_type='application/json')
        trace_id = response.json()['id']

        self.client.post(reverse(update_url_base, args=[trace_id]), data=json.dumps({
            'assembly_id': self.assembly.id, 'settings': {'stud_spacing_in': 24},
        }), content_type='application/json')

        line_items = LineItem.objects.filter(trace_id=trace_id)
        self.assertEqual(line_items.count(), 1)
        # 10ft wall @ 24" OC: ceil(120/24)+1 = 5+1 = 6
        self.assertEqual(line_items.first().quantity, 6)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OpeningDeductionTests(TestCase):
    """A wall's own stud count should shrink where an opening is cut into it -
    those studs are replaced by the opening's king/jack/cripple studs (from
    the opening's own assembly, generated separately), not counted twice."""

    def setUp(self):
        self.user = User.objects.create_user(email='opening-deduct@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Opening Deduction House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)

        self.stud = MaterialProduct.objects.create(name='Deduct 2x6', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=self.stud, length_ft=16, is_default=True)

        self.assembly = Assembly.objects.create(name='Deduct Test Wall', tool_type='line')
        CalculationRule.objects.create(
            assembly=self.assembly, material=self.stud, role='Stud',
            formula_kind=CalculationRule.FormulaKind.PER_SPACING, extra=1,
            waste_factor=Decimal('0'), order=1,
        )

        # 300px line = 10ft, so 30 pixels per foot.
        self.page.scale_pixels_per_foot = Decimal('30')
        self.page.save(update_fields=['scale_pixels_per_foot'])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'line', 'geometry': [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}],
                'assembly_id': self.assembly.id, 'settings': {'stud_spacing_in': 16},
            }),
            content_type='application/json',
        )
        self.wall = Trace.objects.get(pk=response.json()['id'])

    def _wall_stud_quantity(self):
        return LineItem.objects.get(trace=self.wall).quantity

    def test_baseline_stud_count_with_no_openings(self):
        # 10ft wall @ 16" OC: ceil(120/16)+1 = 8 = 9
        self.assertEqual(self._wall_stud_quantity(), 9)

    def test_attaching_opening_reduces_wall_stud_count(self):
        # 60px opening = 2ft; 8ft remaining: ceil(96/16)+1 = 6+1 = 7
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'opening', 'geometry': [{'x': 100, 'y': 0}, {'x': 160, 'y': 0}],
                'parent_wall_id': self.wall.pk,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self._wall_stud_quantity(), 7)

    def test_detaching_opening_restores_wall_stud_count(self):
        create_response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'opening', 'geometry': [{'x': 100, 'y': 0}, {'x': 160, 'y': 0}],
                'parent_wall_id': self.wall.pk,
            }),
            content_type='application/json',
        )
        opening_id = create_response.json()['id']
        self.assertEqual(self._wall_stud_quantity(), 7)

        response = self.client.post(
            reverse('plans:trace-update', args=[opening_id]),
            data=json.dumps({'parent_wall_id': None}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._wall_stud_quantity(), 9)

    def test_deleting_opening_restores_wall_stud_count(self):
        create_response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'opening', 'geometry': [{'x': 100, 'y': 0}, {'x': 160, 'y': 0}],
                'parent_wall_id': self.wall.pk,
            }),
            content_type='application/json',
        )
        opening_id = create_response.json()['id']
        self.assertEqual(self._wall_stud_quantity(), 7)

        response = self.client.post(reverse('plans:trace-delete', args=[opening_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._wall_stud_quantity(), 9)

    def test_reattaching_opening_to_a_different_wall_updates_both_walls(self):
        second_response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'line', 'geometry': [{'x': 0, 'y': 50}, {'x': 300, 'y': 50}],
                'assembly_id': self.assembly.id, 'settings': {'stud_spacing_in': 16},
            }),
            content_type='application/json',
        )
        second_wall = Trace.objects.get(pk=second_response.json()['id'])
        self.assertEqual(LineItem.objects.get(trace=second_wall).quantity, 9)

        create_response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'opening', 'geometry': [{'x': 100, 'y': 0}, {'x': 160, 'y': 0}],
                'parent_wall_id': self.wall.pk,
            }),
            content_type='application/json',
        )
        opening_id = create_response.json()['id']
        self.assertEqual(self._wall_stud_quantity(), 7)

        response = self.client.post(
            reverse('plans:trace-update', args=[opening_id]),
            data=json.dumps({'parent_wall_id': second_wall.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._wall_stud_quantity(), 9)  # first wall's deduction lifted


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class WallJunctionRegenerationTests(TestCase):
    """Corners and T-intersections between separate wall traces should bump
    the affected walls' stud counts automatically - including when a
    neighboring wall is created or deleted later, not just when a wall's own
    trace is drawn."""

    def setUp(self):
        self.user = User.objects.create_user(email='junction-regen@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Junction Regen House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)

        self.stud = MaterialProduct.objects.create(name='Junction 2x6', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=self.stud, length_ft=16, is_default=True)

        self.assembly = Assembly.objects.create(name='Junction Test Wall', tool_type='line')
        CalculationRule.objects.create(
            assembly=self.assembly, material=self.stud, role='Stud',
            formula_kind=CalculationRule.FormulaKind.PER_SPACING, extra=1,
            corner_stud_count=2, t_intersection_stud_count=1, t_backer_stud_count=3,
            waste_factor=Decimal('0'), order=1,
        )

        # 300px line = 10ft, so 30 pixels per foot.
        self.page.scale_pixels_per_foot = Decimal('30')
        self.page.save(update_fields=['scale_pixels_per_foot'])
        self.client.force_login(self.user)

    def _create_wall(self, geometry):
        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'line', 'geometry': geometry,
                'assembly_id': self.assembly.id, 'settings': {'stud_spacing_in': 16},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        return Trace.objects.get(pk=response.json()['id'])

    def _stud_quantity(self, wall):
        return LineItem.objects.get(trace=wall).quantity

    def test_creating_second_wall_bumps_first_walls_stud_count(self):
        wall_a = self._create_wall([{'x': 0, 'y': 0}, {'x': 300, 'y': 0}])
        # 10ft wall @ 16" OC, no junction yet: ceil(120/16)+1 = 8+1 = 9
        self.assertEqual(self._stud_quantity(wall_a), 9)

        # wall_b meets wall_a's endpoint at a right angle - a corner for both.
        self._create_wall([{'x': 300, 'y': 0}, {'x': 300, 'y': 300}])
        self.assertEqual(self._stud_quantity(wall_a), 9 + 2)  # bumped by corner_stud_count

    def test_deleting_a_wall_removes_the_corner_bonus_from_its_sibling(self):
        wall_a = self._create_wall([{'x': 0, 'y': 0}, {'x': 300, 'y': 0}])
        wall_b = self._create_wall([{'x': 300, 'y': 0}, {'x': 300, 'y': 300}])
        self.assertEqual(self._stud_quantity(wall_a), 11)

        response = self.client.post(reverse('plans:trace-delete', args=[wall_b.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._stud_quantity(wall_a), 9)  # back to baseline, junction gone

    def test_l_shape_as_two_walls_matches_same_l_shape_as_one_polyline(self):
        # PER_SPACING measures a trace's own full length as one continuous
        # run, so a 20ft polyline run and two independent 10ft walls have
        # different BASE stud counts already (an existing, unrelated aspect
        # of how PER_SPACING works) - what this feature guarantees is that
        # the JUNCTION contribution alone is the same either way.
        wall_a = self._create_wall([{'x': 0, 'y': 0}, {'x': 300, 'y': 0}])
        wall_b = self._create_wall([{'x': 300, 'y': 0}, {'x': 300, 'y': 300}])
        baseline_per_wall = 9  # 10ft wall @ 16" OC, no junction: ceil(120/16)+1
        two_wall_junction_extra = (
            (self._stud_quantity(wall_a) - baseline_per_wall) + (self._stud_quantity(wall_b) - baseline_per_wall)
        )
        wall_a.delete()
        wall_b.delete()

        response = self.client.post(
            reverse('plans:trace-create', args=[self.page.pk]),
            data=json.dumps({
                'tool_type': 'polyline',
                'geometry': [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}, {'x': 300, 'y': 300}],
                'assembly_id': self.assembly.id, 'settings': {'stud_spacing_in': 16},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        polyline_wall = Trace.objects.get(pk=response.json()['id'])
        baseline_polyline = 16  # 20ft continuous run @ 16" OC, no junction: ceil(240/16)+1
        polyline_junction_extra = self._stud_quantity(polyline_wall) - baseline_polyline
        self.assertEqual(polyline_junction_extra, two_wall_junction_extra)

    def test_t_intersection_bumps_both_the_partition_and_the_through_wall(self):
        through_wall = self._create_wall([{'x': 0, 'y': 0}, {'x': 300, 'y': 0}])
        self.assertEqual(self._stud_quantity(through_wall), 9)

        partition = self._create_wall([{'x': 150, 'y': 0}, {'x': 150, 'y': 300}])
        self.assertEqual(self._stud_quantity(partition), 9 + 1)  # + t_intersection_stud_count
        self.assertEqual(self._stud_quantity(through_wall), 9 + 3)  # + t_backer_stud_count

    def test_deleting_an_opening_does_not_disturb_unrelated_sibling_walls(self):
        wall_a = self._create_wall([{'x': 0, 'y': 0}, {'x': 300, 'y': 0}])
        baseline = self._stud_quantity(wall_a)

        opening = Trace.objects.create(
            plan_page=self.page, tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 0, 'y': 500}, {'x': 30, 'y': 500}],
        )
        response = self.client.post(reverse('plans:trace-delete', args=[opening.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._stud_quantity(wall_a), baseline)
