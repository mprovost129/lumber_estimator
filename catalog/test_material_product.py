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
