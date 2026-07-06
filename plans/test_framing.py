import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from projects.models import JobSettings, Project

from .framing import build_wall_elevation, validate_wall_member_overrides
from .models import Trace
from .test_traces import make_plan_page


class ValidateWallMemberOverridesTests(TestCase):
    def test_none_is_allowed(self):
        validate_wall_member_overrides(None)  # should not raise

    def test_valid_shape_is_allowed(self):
        validate_wall_member_overrides({
            'edited': {'stud_1': {'x': 10, 'y': 1.5, 'width': 1.5, 'height': 90, 'role': 'Edited stud'}},
            'deleted': ['stud_2', 3],
            'added': [{'id': 'custom_1', 'role': 'Blocking', 'x': 10, 'y': 20, 'width': 16, 'height': 1.5}],
        })  # should not raise

    def test_rejects_non_object_overrides(self):
        with self.assertRaises(ValueError):
            validate_wall_member_overrides(['not', 'an', 'object'])

    def test_rejects_non_list_deleted(self):
        with self.assertRaises(ValueError):
            validate_wall_member_overrides({'deleted': 'stud_1'})

    def test_rejects_non_object_edited(self):
        with self.assertRaises(ValueError):
            validate_wall_member_overrides({'edited': ['stud_1']})

    def test_rejects_non_object_edited_entry(self):
        with self.assertRaises(ValueError):
            validate_wall_member_overrides({'edited': {'stud_1': 'not an object'}})

    def test_rejects_non_numeric_edited_field(self):
        with self.assertRaises(ValueError):
            validate_wall_member_overrides({'edited': {'stud_1': {'x': 'not a number'}}})

    def test_rejects_non_list_added(self):
        with self.assertRaises(ValueError):
            validate_wall_member_overrides({'added': {'id': 'custom_1'}})

    def test_rejects_non_object_added_entry(self):
        with self.assertRaises(ValueError):
            validate_wall_member_overrides({'added': ['not an object']})

    def test_rejects_non_numeric_added_field(self):
        with self.assertRaises(ValueError):
            validate_wall_member_overrides({'added': [{'width': []}]})


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class WallElevationFramingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='framing@example.com', password='testpass123')
        self.project = Project.objects.create(account=self.user.account, name='Framing House')
        JobSettings.objects.create(project=self.project)
        self.page = make_plan_page(self.project)
        self.page.scale_pixels_per_foot = Decimal('10')
        self.page.save(update_fields=['scale_pixels_per_foot'])

    def test_wall_elevation_uses_wall_settings_and_builds_cut_list_layers(self):
        wall = Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 200, 'y': 0}],
            settings={
                'stud_spacing_in': 16,
                'wall_height_in': 96,
                'top_plate_count': 3,
                'bottom_plate_count': 1,
                'interior_drywall': True,
                'exterior_sheathing': True,
                'house_wrap': False,
                'siding': True,
            },
        )

        model = build_wall_elevation(wall)

        self.assertEqual(model['length_ft'], 20.0)
        self.assertEqual(model['height_in'], 96)
        self.assertEqual(model['top_plate_count'], 3)
        self.assertEqual(model['summary']['roles']['Top plate'], 3)
        self.assertTrue(any(layer['key'] == 'drywall' for layer in model['layers']))
        self.assertFalse(any(layer['key'] == 'wrap' for layer in model['layers']))
        self.assertTrue(any(row['role'] == 'Top plate' for row in model['cut_list']))

    def test_attached_opening_projects_into_wall_with_header_and_sill_settings(self):
        wall = Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 200, 'y': 0}],
            settings={'stud_spacing_in': 16, 'wall_height_in': 108},
        )
        Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 60, 'y': -5}, {'x': 100, 'y': 5}],
            parent_wall=wall,
            settings={
                'opening_type': 'window',
                'sill_height_in': 42,
                'rough_height_in': 36,
                'header_depth_in': 7.25,
            },
        )

        model = build_wall_elevation(wall)

        self.assertEqual(model['summary']['opening_count'], 1)
        opening = model['openings'][0]
        self.assertEqual(opening['width_in'], 48.0)
        self.assertEqual(opening['sill_height_in'], 42)
        self.assertEqual(opening['rough_height_in'], 36)
        self.assertTrue(any(member['role'] == 'Header' for member in model['members']))
        self.assertTrue(any(member['role'] == 'Rough sill' for member in model['members']))

    def test_unattached_nearby_opening_is_not_included(self):
        wall = Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 200, 'y': 0}],
            settings={'stud_spacing_in': 16, 'wall_height_in': 108},
        )
        # Geometrically right on the wall line, but never explicitly attached -
        # proves attachment is no longer a proximity guess.
        Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 60, 'y': 0}, {'x': 100, 'y': 0}],
            settings={'opening_type': 'window'},
        )

        model = build_wall_elevation(wall)

        self.assertEqual(model['summary']['opening_count'], 0)

    def test_explicitly_attached_opening_far_from_wall_is_still_included(self):
        wall = Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 200, 'y': 0}],
            settings={'stud_spacing_in': 16, 'wall_height_in': 108},
        )
        # 500px away (50ft at this scale) - would have failed the old 2ft
        # proximity tolerance, but an explicit attachment is never rejected.
        far_opening = Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 60, 'y': 500}, {'x': 100, 'y': 505}],
            parent_wall=wall,
            settings={'opening_type': 'window'},
        )

        model = build_wall_elevation(wall)

        self.assertEqual(model['summary']['opening_count'], 1)
        self.assertEqual(model['openings'][0]['id'], far_opening.id)

    def test_polyline_wall_shows_attached_openings(self):
        wall = Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.POLYLINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 200, 'y': 0}],
            settings={'stud_spacing_in': 16, 'wall_height_in': 108},
        )
        Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 60, 'y': -5}, {'x': 100, 'y': 5}],
            parent_wall=wall,
            settings={'opening_type': 'window', 'sill_height_in': 42, 'rough_height_in': 36},
        )

        model = build_wall_elevation(wall)

        self.assertEqual(model['summary']['opening_count'], 1)

    def test_multi_segment_polyline_attaches_opening_on_second_segment(self):
        # An L-shaped wall: 10ft east, then 10ft north (scale is 10 px/ft).
        wall = Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.POLYLINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 100, 'y': 0}, {'x': 100, 'y': 100}],
            settings={'stud_spacing_in': 16, 'wall_height_in': 108},
        )
        # This opening sits right against the second segment (x=100), well off
        # the first segment (y=0) - only correct per-segment projection finds it.
        Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.OPENING,
            geometry=[{'x': 95, 'y': 40}, {'x': 105, 'y': 60}],
            parent_wall=wall,
            settings={'opening_type': 'window'},
        )

        model = build_wall_elevation(wall)

        self.assertEqual(model['summary']['opening_count'], 1)
        opening = model['openings'][0]
        # 10ft (first segment) + 4ft to 6ft along the second segment = 14ft-16ft = 168in-192in.
        self.assertEqual(opening['left_in'], 168.0)
        self.assertEqual(opening['right_in'], 192.0)

    def test_wall_member_overrides_edit_delete_and_add_members(self):
        wall = Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 120, 'y': 0}],
            settings={
                'stud_spacing_in': 16,
                'wall_height_in': 96,
                'wall_member_overrides': {
                    'edited': {
                        'stud_1': {'x': 18, 'y': 1.5, 'width': 1.5, 'height': 80, 'role': 'Edited stud'},
                    },
                    'deleted': ['stud_2'],
                    'added': [
                        {'id': 'custom_block_1', 'role': 'Custom blocking', 'x': 48, 'y': 48, 'width': 16, 'height': 1.5},
                    ],
                },
            },
        )

        model = build_wall_elevation(wall)
        members_by_id = {member['id']: member for member in model['members']}

        self.assertEqual(members_by_id['stud_1']['role'], 'Edited stud')
        self.assertEqual(members_by_id['stud_1']['height'], 80.0)
        self.assertEqual(members_by_id['stud_1']['source'], 'edited')
        self.assertNotIn('stud_2', members_by_id)
        self.assertEqual(members_by_id['custom_block_1']['role'], 'Custom blocking')
        self.assertEqual(members_by_id['custom_block_1']['source'], 'custom')
        self.assertTrue(any(row['role'] == 'Custom blocking' for row in model['cut_list']))

    def test_malformed_overrides_are_skipped_not_raised(self):
        # This shape could never pass validate_wall_member_overrides(), but the
        # read path must still degrade gracefully (e.g. for data saved before
        # validation existed) rather than 500ing the whole wall elevation.
        wall = Trace.objects.create(
            plan_page=self.page,
            tool_type=Trace.ToolType.LINE,
            geometry=[{'x': 0, 'y': 0}, {'x': 120, 'y': 0}],
            settings={
                'stud_spacing_in': 16,
                'wall_height_in': 96,
                'wall_member_overrides': {
                    'deleted': 'not-a-list',
                    'edited': {'stud_1': 'not-an-object', 'stud_2': {'x': 'not-a-number'}},
                    'added': ['not-an-object', {'width': [], 'role': 'Bad width'}],
                },
            },
        )

        model = build_wall_elevation(wall)  # should not raise

        self.assertTrue(any(member['id'] == 'stud_1' for member in model['members']))
