from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Account
from catalog.models import MaterialLength, MaterialProduct


class MaterialProductSlugTests(TestCase):
    def test_slug_auto_generated_from_name(self):
        product = MaterialProduct.objects.create(name='Deck Screws 3in')
        self.assertEqual(product.slug, 'deck-screws-3in')

    def test_global_slugs_must_be_unique(self):
        MaterialProduct.objects.create(name='Deck Screws 3in')
        with self.assertRaises(IntegrityError), transaction.atomic():
            MaterialProduct.objects.create(name='Deck Screws 3in', slug='deck-screws-3in')

    def test_two_accounts_can_reuse_the_same_slug(self):
        account_a = Account.objects.create(name='A')
        account_b = Account.objects.create(name='B')
        MaterialProduct.objects.create(account=account_a, name='Custom Bracket')
        product_b = MaterialProduct.objects.create(account=account_b, name='Custom Bracket')
        self.assertEqual(product_b.slug, 'custom-bracket')


class MaterialProductInputTypeTests(TestCase):
    def test_supported_input_types_default_to_primary_input_type(self):
        product = MaterialProduct.objects.create(name='Default Support', input_type=MaterialProduct.InputType.EACH)
        self.assertEqual(product.normalized_supported_input_types(), [MaterialProduct.InputType.EACH])

    def test_box_requires_quantity_per_box(self):
        product = MaterialProduct(name='Framing Nails', input_type=MaterialProduct.InputType.BOX)
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_non_box_rejects_quantity_per_box(self):
        product = MaterialProduct(
            name='Framing Nails', input_type=MaterialProduct.InputType.EACH, quantity_per_box=100,
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_default_input_type_must_be_supported(self):
        product = MaterialProduct(
            name='Split Mode Material',
            input_type=MaterialProduct.InputType.EACH,
            supported_input_types=[MaterialProduct.InputType.FT],
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_boxes_needed_rounds_up(self):
        product = MaterialProduct.objects.create(
            name='Deck Screws 3in', input_type=MaterialProduct.InputType.BOX, quantity_per_box=100,
        )
        self.assertEqual(product.boxes_needed(55), 1)
        self.assertEqual(product.boxes_needed(101), 2)
        self.assertEqual(product.boxes_needed(200), 2)

    def test_boxes_needed_raises_for_non_box_material(self):
        product = MaterialProduct.objects.create(name='Test Beam', input_type=MaterialProduct.InputType.FT)
        with self.assertRaises(ValueError):
            product.boxes_needed(10)

    def test_stock_length_for_picks_smallest_covering_length(self):
        product = MaterialProduct.objects.create(name='Test Joist', input_type=MaterialProduct.InputType.FT)
        for length_ft in (8, 10, 12, 14, 16):
            MaterialLength.objects.create(product=product, length_ft=length_ft)
        self.assertEqual(product.stock_length_for(13), 14)
        self.assertEqual(product.stock_length_for(8), 8)

    def test_stock_length_for_raises_when_nothing_covers_it(self):
        product = MaterialProduct.objects.create(name='Test Joist Short', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=product, length_ft=8)
        with self.assertRaises(ValueError):
            product.stock_length_for(20)

    def test_length_cannot_be_added_to_non_ft_material(self):
        product = MaterialProduct.objects.create(name='Deck Screws 3in', input_type=MaterialProduct.InputType.EACH)
        length = MaterialLength(product=product, length_ft=8)
        with self.assertRaises(ValidationError):
            length.full_clean()

    def test_default_length_ft_returns_the_flagged_length(self):
        product = MaterialProduct.objects.create(name='Test Plate Stock', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=product, length_ft=8)
        MaterialLength.objects.create(product=product, length_ft=16, is_default=True)
        MaterialLength.objects.create(product=product, length_ft=24)
        self.assertEqual(product.default_length_ft, 16)

    def test_material_can_support_ft_without_ft_being_default_input_type(self):
        product = MaterialProduct.objects.create(
            name='Multi Mode Joist',
            input_type=MaterialProduct.InputType.EACH,
            supported_input_types=[MaterialProduct.InputType.EACH, MaterialProduct.InputType.FT],
        )
        MaterialLength.objects.create(product=product, length_ft=12, is_default=True)
        MaterialLength.objects.create(product=product, length_ft=16)
        self.assertEqual(product.default_length_ft, 12)
        self.assertEqual(product.stock_length_for(13), 16)

    def test_material_can_support_box_without_box_being_default_input_type(self):
        product = MaterialProduct.objects.create(
            name='Multi Mode Fasteners',
            input_type=MaterialProduct.InputType.EACH,
            supported_input_types=[MaterialProduct.InputType.EACH, MaterialProduct.InputType.BOX],
            quantity_per_box=100,
        )
        self.assertEqual(product.boxes_needed(101), 2)

    def test_default_length_ft_raises_when_no_default_set(self):
        product = MaterialProduct.objects.create(name='Test No Default', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=product, length_ft=8)
        with self.assertRaises(ValueError):
            product.default_length_ft

    def test_default_length_ft_raises_for_non_ft_material(self):
        product = MaterialProduct.objects.create(name='Deck Screws 4in', input_type=MaterialProduct.InputType.EACH)
        with self.assertRaises(ValueError):
            product.default_length_ft

    def test_stock_length_for_supports_precut_stud_fractional_lengths(self):
        # 92-5/8 in and 104-5/8 in precuts, exact at 5 decimal places in feet.
        product = MaterialProduct.objects.create(name='Test Stud', input_type=MaterialProduct.InputType.FT)
        MaterialLength.objects.create(product=product, length_ft=Decimal('7.71875'))
        MaterialLength.objects.create(product=product, length_ft=Decimal('8.71875'))
        MaterialLength.objects.create(product=product, length_ft=10)
        self.assertEqual(product.stock_length_for(Decimal('7.71875')), Decimal('7.71875'))
        self.assertEqual(product.stock_length_for(Decimal('8')), Decimal('8.71875'))

    def test_material_length_str_shows_fraction_and_strips_trailing_zeros(self):
        product = MaterialProduct.objects.create(name='Test Stud Str', input_type=MaterialProduct.InputType.FT)
        precut = MaterialLength.objects.create(product=product, length_ft=Decimal('7.71875'))
        whole = MaterialLength.objects.create(product=product, length_ft=10)
        self.assertEqual(str(precut), 'Test Stud Str - 7.71875 ft')
        self.assertEqual(str(whole), 'Test Stud Str - 10 ft')


class PiecesForLengthTests(TestCase):
    """max_length_ft and pieces_for_length: how a member is split into stock
    pieces, including splicing when it is longer than the longest stock."""

    def setUp(self):
        self.material = MaterialProduct.objects.create(
            name='Beam Stock', input_type=MaterialProduct.InputType.FT,
        )
        for length in (12, 16, 20):
            MaterialLength.objects.create(
                product=self.material, length_ft=length, is_default=(length == 16),
            )

    def test_max_length_ft_returns_longest_stock(self):
        self.assertEqual(self.material.max_length_ft, Decimal('20'))

    def test_pieces_for_length_single_piece_when_it_fits(self):
        # 14 ft needs one piece, cut from the smallest covering stock (16 ft).
        self.assertEqual(self.material.pieces_for_length(14), (1, Decimal('16')))

    def test_pieces_for_length_exact_stock_is_one_piece(self):
        self.assertEqual(self.material.pieces_for_length(20), (1, Decimal('20')))

    def test_pieces_for_length_splices_when_over_length(self):
        # 44 ft: ceil(44 / 20) = 3 pieces of the longest (20 ft) stock.
        self.assertEqual(self.material.pieces_for_length(44), (3, Decimal('20')))

    def test_max_length_ft_raises_for_non_ft_material(self):
        each = MaterialProduct.objects.create(
            name='Bracket', input_type=MaterialProduct.InputType.EACH,
        )
        with self.assertRaises(ValueError):
            _ = each.max_length_ft


class SeededPrecutStudLengthTests(TestCase):
    """Spot-checks against the actual migrated seed data (0006), not a fresh
    fixture, so a future migration can't silently drop these precut lengths."""

    def _lengths_for(self, dimension):
        product = MaterialProduct.objects.get(
            account__isnull=True, species='SPF', grade='#2', nominal_dimension=dimension,
        )
        return set(product.lengths.values_list('length_ft', flat=True))

    def test_2x4_spf_has_both_precut_lengths(self):
        lengths = self._lengths_for('2x4')
        self.assertIn(Decimal('7.71875'), lengths)
        self.assertIn(Decimal('8.71875'), lengths)

    def test_2x6_spf_has_both_precut_lengths(self):
        lengths = self._lengths_for('2x6')
        self.assertIn(Decimal('7.71875'), lengths)
        self.assertIn(Decimal('8.71875'), lengths)

    def test_existing_default_length_untouched(self):
        product = MaterialProduct.objects.get(
            account__isnull=True, species='SPF', grade='#2', nominal_dimension='2x4',
        )
        default = product.lengths.get(is_default=True)
        self.assertEqual(default.length_ft, 16)


class MaterialProductVisibilityTests(TestCase):
    def test_visible_to_includes_global_and_own_account_only(self):
        account_a = Account.objects.create(name='A')
        account_b = Account.objects.create(name='B')
        global_product = MaterialProduct.objects.create(name='Test Global Material')
        product_a = MaterialProduct.objects.create(account=account_a, name='A Custom')
        product_b = MaterialProduct.objects.create(account=account_b, name='B Custom')

        visible = MaterialProduct.objects.visible_to(account_a)
        self.assertIn(global_product, visible)
        self.assertIn(product_a, visible)
        self.assertNotIn(product_b, visible)
