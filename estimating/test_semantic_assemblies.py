from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Account

from .models import Assembly


class AssemblyCleanValidationTests(TestCase):
    def test_wall_subtype_and_beam_type_cannot_both_be_set(self):
        assembly = Assembly(
            name='Bad Combo', tool_type='line',
            wall_subtype=Assembly.WallSubtype.EXTERIOR, beam_type=Assembly.BeamType.FLUSH,
        )
        with self.assertRaises(ValidationError):
            assembly.clean()

    def test_opening_kind_requires_opening_tool_type(self):
        assembly = Assembly(name='Bad Opening Kind', tool_type='line', opening_kind=Assembly.OpeningKind.WINDOW)
        with self.assertRaises(ValidationError):
            assembly.clean()

    def test_opening_kind_allowed_on_opening_tool_type(self):
        assembly = Assembly(name='Good Opening Kind', tool_type='opening', opening_kind=Assembly.OpeningKind.WINDOW)
        assembly.clean()  # must not raise

    def test_wall_subtype_alone_is_fine_on_a_line_assembly(self):
        assembly = Assembly(name='Good Wall', tool_type='line', wall_subtype=Assembly.WallSubtype.EXTERIOR)
        assembly.clean()  # must not raise


class AssemblyUniquenessConstraintTests(TestCase):
    """The seed migration already occupies all 6 (opening_kind, wall_subtype)
    pairs among global assemblies, so these tests exercise the constraint
    against that existing data rather than assuming an empty table."""

    def test_two_global_assemblies_cannot_share_opening_kind_and_wall_subtype(self):
        # 'Window Opening - Exterior Wall Header' already occupies this pair.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Assembly.objects.create(
                    name='Duplicate Window', tool_type='opening',
                    opening_kind=Assembly.OpeningKind.WINDOW, wall_subtype=Assembly.WallSubtype.EXTERIOR,
                )

    def test_two_assemblies_owned_by_the_same_account_cannot_share_the_pair(self):
        account = Account.objects.create(name='Constraint Test Co')
        Assembly.objects.create(
            account=account, name='Window A', tool_type='opening',
            opening_kind=Assembly.OpeningKind.DOOR, wall_subtype=Assembly.WallSubtype.INTERIOR_BEARING,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Assembly.objects.create(
                    account=account, name='Window B', tool_type='opening',
                    opening_kind=Assembly.OpeningKind.DOOR, wall_subtype=Assembly.WallSubtype.INTERIOR_BEARING,
                )

    def test_global_and_a_different_accounts_assembly_can_share_the_pair(self):
        account = Account.objects.create(name='Other Constraint Co')
        # A global assembly already occupies (window, interior_non_bearing) -
        # an account-owned assembly sharing that same pair must not conflict.
        Assembly.objects.create(
            account=account, name='Account Window', tool_type='opening',
            opening_kind=Assembly.OpeningKind.WINDOW, wall_subtype=Assembly.WallSubtype.INTERIOR_NON_BEARING,
        )


class SeedAssemblyClassificationTests(TestCase):
    def test_new_assemblies_are_classified_as_expected(self):
        expectations = {
            '2x6 Interior Bearing Wall - 16 in OC': {'wall_subtype': 'interior_bearing'},
            '2x4 Interior Non-Bearing Wall - 16 in OC': {'wall_subtype': 'interior_non_bearing'},
            'LVL Beam - Flush (Double 1-3/4x11-7/8)': {'beam_type': 'flush'},
            'LVL Beam - Dropped (Double 1-3/4x11-7/8)': {'beam_type': 'dropped'},
            'Window Opening - Exterior Wall Header': {'opening_kind': 'window', 'wall_subtype': 'exterior'},
            'Door Opening - Exterior Wall Header': {'opening_kind': 'door', 'wall_subtype': 'exterior'},
            'Window Opening - Interior Bearing Wall Header': {'opening_kind': 'window', 'wall_subtype': 'interior_bearing'},
            'Door Opening - Interior Bearing Wall Header': {'opening_kind': 'door', 'wall_subtype': 'interior_bearing'},
            'Window Opening - Interior Non-Bearing Wall (Light)': {'opening_kind': 'window', 'wall_subtype': 'interior_non_bearing'},
            'Door Opening - Interior Non-Bearing Wall (Light)': {'opening_kind': 'door', 'wall_subtype': 'interior_non_bearing'},
        }
        for name, tags in expectations.items():
            with self.subTest(assembly=name):
                assembly = Assembly.objects.get(name=name, account__isnull=True)
                for field, value in tags.items():
                    with self.subTest(assembly=name, field=field):
                        self.assertEqual(getattr(assembly, field), value)

    def test_exterior_wall_assembly_is_tagged(self):
        assembly = Assembly.objects.get(name='2x6 Exterior Wall on Slab - 16 in OC', account__isnull=True)
        self.assertEqual(assembly.wall_subtype, 'exterior')

    def test_ambiguous_legacy_assemblies_remain_unclassified(self):
        for name in [
            '2x4 Wall - 16 in OC', '2x6 Wall - 16 in OC', 'LVL Beam 1-3/4x11-7/8 (Double)',
            'Window/Door Opening - 2x10 Header (2x6 Wall)',
        ]:
            with self.subTest(assembly=name):
                assembly = Assembly.objects.get(name=name, account__isnull=True)
                self.assertIsNone(assembly.wall_subtype)
                self.assertIsNone(assembly.opening_kind)
                self.assertIsNone(assembly.beam_type)
                self.assertIn('Legacy', assembly.description)


class DefaultAssemblyTests(TestCase):
    """The seeded is_default flags let the viewer auto-load an assembly when a
    semantic tool is picked. Each semantic tool filters the assembly list a
    specific way, so within every one of those filtered sets there must be
    exactly one default, otherwise the viewer cannot pick unambiguously."""

    def _globals(self):
        return Assembly.objects.filter(account__isnull=True)

    def test_each_wall_subtype_has_exactly_one_default(self):
        for subtype in ('exterior', 'interior_bearing', 'interior_non_bearing'):
            count = self._globals().filter(tool_type='line', wall_subtype=subtype, is_default=True).count()
            self.assertEqual(count, 1, f'wall subtype {subtype} should have one default, found {count}')

    def test_each_beam_type_has_exactly_one_default(self):
        for beam_type in ('flush', 'dropped'):
            count = self._globals().filter(tool_type='line', beam_type=beam_type, is_default=True).count()
            self.assertEqual(count, 1, f'beam type {beam_type} should have one default, found {count}')

    def test_joist_area_set_has_exactly_one_default(self):
        # The Joist tool filters area assemblies to floor/ceiling/roof.
        count = self._globals().filter(
            tool_type='area', category__in=('floor_system', 'ceiling', 'roof'), is_default=True,
        ).count()
        self.assertEqual(count, 1)

    def test_count_tool_has_exactly_one_default(self):
        # The Column tool has no variant filter, so it relies on a single
        # default across all count assemblies.
        count = self._globals().filter(tool_type='count', is_default=True).count()
        self.assertEqual(count, 1)

    def test_each_opening_kind_has_exactly_one_default(self):
        for opening_kind in ('window', 'door'):
            count = self._globals().filter(
                tool_type='opening', opening_kind=opening_kind, is_default=True,
            ).count()
            self.assertEqual(count, 1, f'opening kind {opening_kind} should have one default, found {count}')

    def test_raw_line_set_is_intentionally_ambiguous(self):
        # More than one default across the whole line tool_type is expected
        # (each wall/beam variant has its own). The viewer only auto-selects
        # when a filtered set has exactly one, so the raw Line tool stays manual.
        self.assertGreater(self._globals().filter(tool_type='line', is_default=True).count(), 1)
