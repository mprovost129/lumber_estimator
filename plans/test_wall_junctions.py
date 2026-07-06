import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from projects.models import JobSettings, Project

from .models import Trace
from .test_traces import make_plan_page
from .wall_junctions import could_share_a_junction, detect_wall_junctions

User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class WallJunctionDetectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='junction@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Junction House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.page.scale_pixels_per_foot = Decimal('10')
        self.page.save(update_fields=['scale_pixels_per_foot'])

    def _wall(self, geometry, tool_type=Trace.ToolType.LINE):
        return Trace.objects.create(plan_page=self.page, tool_type=tool_type, geometry=geometry)

    def test_two_walls_meeting_at_a_right_angle_are_a_corner(self):
        a = self._wall([{'x': 0, 'y': 0}, {'x': 100, 'y': 0}])
        b = self._wall([{'x': 100, 'y': 0}, {'x': 100, 'y': 100}])
        self.assertEqual(detect_wall_junctions(a)['corner_count'], 1)
        self.assertEqual(detect_wall_junctions(b)['corner_count'], 1)

    def test_walls_far_apart_have_no_junction(self):
        a = self._wall([{'x': 0, 'y': 0}, {'x': 100, 'y': 0}])
        b = self._wall([{'x': 0, 'y': 500}, {'x': 100, 'y': 500}])
        self.assertEqual(detect_wall_junctions(a), {'corner_count': 0, 'partition_t_count': 0, 'through_t_count': 0})
        self.assertEqual(detect_wall_junctions(b), {'corner_count': 0, 'partition_t_count': 0, 'through_t_count': 0})

    def test_endpoint_just_outside_tolerance_is_not_a_corner(self):
        # Tolerance is 0.5ft = 5px at this page's 10px/ft scale.
        a = self._wall([{'x': 0, 'y': 0}, {'x': 100, 'y': 0}])
        self._wall([{'x': 110, 'y': 0}, {'x': 110, 'y': 100}])
        self.assertEqual(detect_wall_junctions(a)['corner_count'], 0)

    def test_two_collinear_walls_sharing_an_endpoint_are_not_a_corner(self):
        # A straight wall split into two trace segments (e.g. to change
        # material partway through) must not be falsely flagged as a corner.
        a = self._wall([{'x': 0, 'y': 0}, {'x': 100, 'y': 0}])
        b = self._wall([{'x': 100, 'y': 0}, {'x': 200, 'y': 0}])
        self.assertEqual(detect_wall_junctions(a)['corner_count'], 0)
        self.assertEqual(detect_wall_junctions(b)['corner_count'], 0)

    def test_polyline_bend_counts_as_two_corner_occurrences(self):
        wall = self._wall(
            [{'x': 0, 'y': 0}, {'x': 100, 'y': 0}, {'x': 100, 'y': 100}], tool_type=Trace.ToolType.POLYLINE,
        )
        self.assertEqual(detect_wall_junctions(wall)['corner_count'], 2)

    def test_polyline_with_collinear_points_has_no_false_positive_bend(self):
        wall = self._wall(
            [{'x': 0, 'y': 0}, {'x': 50, 'y': 0}, {'x': 100, 'y': 0}], tool_type=Trace.ToolType.POLYLINE,
        )
        self.assertEqual(detect_wall_junctions(wall)['corner_count'], 0)

    def test_polyline_with_near_duplicate_point_does_not_crash(self):
        wall = self._wall(
            [{'x': 0, 'y': 0}, {'x': 50, 'y': 0}, {'x': 50.0000001, 'y': 0}, {'x': 100, 'y': 100}],
            tool_type=Trace.ToolType.POLYLINE,
        )
        detect_wall_junctions(wall)  # must not raise

    def test_l_layout_as_two_lines_matches_same_layout_as_one_polyline(self):
        a = self._wall([{'x': 0, 'y': 0}, {'x': 100, 'y': 0}])
        b = self._wall([{'x': 100, 'y': 0}, {'x': 100, 'y': 100}])
        two_line_total = detect_wall_junctions(a)['corner_count'] + detect_wall_junctions(b)['corner_count']
        a.delete()
        b.delete()

        polyline = self._wall(
            [{'x': 0, 'y': 0}, {'x': 100, 'y': 0}, {'x': 100, 'y': 100}], tool_type=Trace.ToolType.POLYLINE,
        )
        polyline_total = detect_wall_junctions(polyline)['corner_count']
        self.assertEqual(two_line_total, polyline_total)

    def test_endpoint_landing_on_another_walls_span_is_a_t_intersection(self):
        partition = self._wall([{'x': 50, 'y': 0}, {'x': 50, 'y': 100}])
        through_wall = self._wall([{'x': 0, 'y': 0}, {'x': 100, 'y': 0}])
        self.assertEqual(detect_wall_junctions(partition)['partition_t_count'], 1)
        self.assertEqual(detect_wall_junctions(through_wall)['through_t_count'], 1)
        self.assertEqual(detect_wall_junctions(partition)['corner_count'], 0)
        self.assertEqual(detect_wall_junctions(through_wall)['corner_count'], 0)

    def test_endpoint_on_another_polylines_internal_bend_is_a_corner_not_invisible(self):
        self._wall(
            [{'x': 0, 'y': 0}, {'x': 100, 'y': 0}, {'x': 100, 'y': 100}], tool_type=Trace.ToolType.POLYLINE,
        )
        touching_wall = self._wall([{'x': 100, 'y': 0}, {'x': 200, 'y': 50}])
        self.assertEqual(detect_wall_junctions(touching_wall)['corner_count'], 1)
        self.assertEqual(detect_wall_junctions(touching_wall)['partition_t_count'], 0)

    def test_three_way_junction_is_not_multiply_counted(self):
        a = self._wall([{'x': 0, 'y': 0}, {'x': 100, 'y': 0}])
        b = self._wall([{'x': 100, 'y': 0}, {'x': 200, 'y': 0}])
        c = self._wall([{'x': 100, 'y': 0}, {'x': 100, 'y': 100}])
        self.assertEqual(detect_wall_junctions(a)['corner_count'], 1)
        self.assertEqual(detect_wall_junctions(b)['corner_count'], 1)
        self.assertEqual(detect_wall_junctions(c)['corner_count'], 1)

    def test_uncalibrated_page_returns_all_zero(self):
        self.page.scale_pixels_per_foot = None
        self.page.save(update_fields=['scale_pixels_per_foot'])
        a = self._wall([{'x': 0, 'y': 0}, {'x': 100, 'y': 0}])
        self.assertEqual(detect_wall_junctions(a), {'corner_count': 0, 'partition_t_count': 0, 'through_t_count': 0})

    def test_non_wall_tool_types_return_all_zero(self):
        opening = self._wall([{'x': 0, 'y': 0}, {'x': 10, 'y': 0}], tool_type=Trace.ToolType.OPENING)
        count_trace = self._wall([{'x': 0, 'y': 0}], tool_type=Trace.ToolType.COUNT)
        self.assertEqual(detect_wall_junctions(opening)['corner_count'], 0)
        self.assertEqual(detect_wall_junctions(count_trace)['corner_count'], 0)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class CouldShareAJunctionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='prefilter@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Prefilter House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.page.scale_pixels_per_foot = Decimal('10')
        self.page.save(update_fields=['scale_pixels_per_foot'])

    def _wall(self, geometry):
        return Trace.objects.create(plan_page=self.page, tool_type=Trace.ToolType.LINE, geometry=geometry)

    def test_nearby_wall_could_share_a_junction(self):
        a = self._wall([{'x': 0, 'y': 0}, {'x': 100, 'y': 0}])
        b = self._wall([{'x': 100, 'y': 0}, {'x': 100, 'y': 100}])
        self.assertTrue(could_share_a_junction(a, b))

    def test_far_wall_could_not_share_a_junction(self):
        a = self._wall([{'x': 0, 'y': 0}, {'x': 100, 'y': 0}])
        b = self._wall([{'x': 0, 'y': 1000}, {'x': 100, 'y': 1000}])
        self.assertFalse(could_share_a_junction(a, b))
