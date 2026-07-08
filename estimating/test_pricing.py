import csv
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from billing.models import EstimateAccessGrant
from catalog.models import MaterialPrice, MaterialProduct
from estimating.models import LineItem
from projects.models import Estimate, Project

User = get_user_model()


class MaterialPricingTests(TestCase):
    """Optional per-account pricing: quantities roll up to a bid total when
    unit costs exist, and the estimate stays a clean material list when they
    do not. Prices never cross accounts and never touch the global catalog."""

    def setUp(self):
        self.user = User.objects.create_user(email='pricer@example.com', password='testpass123')
        self.account = self.user.account
        self.project = Project.objects.create(account=self.account, name='Priced House')
        self.estimate = Estimate.objects.create(project=self.project)
        self.stud = MaterialProduct.objects.create(
            name='Priced 2x6', input_type=MaterialProduct.InputType.FT, nominal_dimension='2x6',
        )
        self.hanger = MaterialProduct.objects.create(
            name='Priced Hanger', input_type=MaterialProduct.InputType.EACH,
        )
        LineItem.objects.create(
            estimate=self.estimate, material=self.stud, role='Stud',
            length_ft=Decimal('10'), quantity=9, source=LineItem.Source.TOOL,
        )
        LineItem.objects.create(
            estimate=self.estimate, material=self.hanger, role='Hanger',
            quantity=4, source=LineItem.Source.TOOL,
        )
        self.client.force_login(self.user)

    def _grant_access(self):
        EstimateAccessGrant.objects.create(
            estimate=self.estimate, purchased_by=self.user,
            status=EstimateAccessGrant.Status.PAID, stripe_checkout_session_id='cs_priced',
        )

    def test_detail_shows_no_bid_total_when_unpriced(self):
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate.pk]))
        self.assertNotContains(response, 'Material total')
        self.assertContains(response, 'to see a bid total')

    def test_detail_rolls_up_bid_total_when_priced(self):
        MaterialPrice.objects.create(account=self.account, material=self.stud, unit_cost=Decimal('7.50'))
        MaterialPrice.objects.create(account=self.account, material=self.hanger, unit_cost=Decimal('2.25'))
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate.pk]))
        # 9 * 7.50 + 4 * 2.25 = 67.50 + 9.00 = 76.50
        self.assertContains(response, 'Material total')
        self.assertContains(response, '76.50')

    def test_partial_pricing_shows_total_of_priced_rows_only(self):
        MaterialPrice.objects.create(account=self.account, material=self.stud, unit_cost=Decimal('7.50'))
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate.pk]))
        self.assertContains(response, 'Material total')
        self.assertContains(response, '67.50')  # only the priced stud row

    def test_csv_gains_cost_columns_when_priced(self):
        MaterialPrice.objects.create(account=self.account, material=self.stud, unit_cost=Decimal('7.50'))
        self._grant_access()
        response = self.client.get(reverse('estimating:estimate-csv', args=[self.estimate.pk]))
        rows = list(csv.reader(response.content.decode().splitlines()))
        self.assertIn('Unit Cost', rows[0])
        self.assertIn('Extended Cost', rows[0])
        self.assertTrue(any('Material total' in row for row in rows))

    def test_csv_omits_cost_columns_when_unpriced(self):
        self._grant_access()
        response = self.client.get(reverse('estimating:estimate-csv', args=[self.estimate.pk]))
        rows = list(csv.reader(response.content.decode().splitlines()))
        self.assertNotIn('Unit Cost', rows[0])

    def test_prices_never_leak_across_accounts(self):
        other = User.objects.create_user(email='other-pricer@example.com', password='testpass123')
        MaterialPrice.objects.create(account=other.account, material=self.stud, unit_cost=Decimal('99.00'))
        # This account has not priced anything, so its estimate stays unpriced.
        response = self.client.get(reverse('estimating:estimate-detail', args=[self.estimate.pk]))
        self.assertNotContains(response, 'Material total')
        self.assertNotContains(response, '99.00')


class MaterialFormPricingTests(TestCase):
    """The Library material create/edit form doubles as the pricing entry
    point, upserting the account's private MaterialPrice."""

    def setUp(self):
        self.user = User.objects.create_user(email='libpricer@example.com', password='testpass123')
        self.account = self.user.account
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        payload = {
            'name': 'Form Priced Stud',
            'category': MaterialProduct.Category.STUDS,
            'species': 'SPF', 'grade': '#2', 'nominal_dimension': '2x4',
            'supported_input_types': [MaterialProduct.InputType.EACH],
            'input_type': MaterialProduct.InputType.EACH,
        }
        payload.update(overrides)
        return payload

    def test_creating_a_material_with_a_cost_saves_a_price(self):
        self.client.post(reverse('estimating:material-create'), self._payload(unit_cost='3.75'))
        material = MaterialProduct.objects.get(account=self.account, name='Form Priced Stud')
        price = MaterialPrice.objects.get(account=self.account, material=material)
        self.assertEqual(price.unit_cost, Decimal('3.75'))

    def test_clearing_the_cost_removes_the_price(self):
        material = MaterialProduct.objects.create(
            account=self.account, name='Form Priced Stud',
            input_type=MaterialProduct.InputType.EACH,
        )
        MaterialPrice.objects.create(account=self.account, material=material, unit_cost=Decimal('3.75'))
        self.client.post(
            reverse('estimating:material-update', args=[material.pk]),
            self._payload(unit_cost=''),
        )
        self.assertFalse(MaterialPrice.objects.filter(account=self.account, material=material).exists())

    def test_price_edit_is_scoped_to_the_editing_account(self):
        material = MaterialProduct.objects.create(
            account=self.account, name='Form Priced Stud',
            input_type=MaterialProduct.InputType.EACH,
        )
        other = User.objects.create_user(email='other-lib@example.com', password='testpass123')
        MaterialPrice.objects.create(account=other.account, material=material, unit_cost=Decimal('50.00'))
        self.client.post(
            reverse('estimating:material-update', args=[material.pk]),
            self._payload(unit_cost='4.00'),
        )
        self.assertEqual(
            MaterialPrice.objects.get(account=self.account, material=material).unit_cost, Decimal('4.00'),
        )
        # The other account's price is untouched.
        self.assertEqual(
            MaterialPrice.objects.get(account=other.account, material=material).unit_cost, Decimal('50.00'),
        )


class MaterialPriceEndpointTests(TestCase):
    """The inline Library price form works for global stock materials too,
    without ever mutating the shared catalog."""

    def setUp(self):
        self.user = User.objects.create_user(email='inline@example.com', password='testpass123')
        self.account = self.user.account
        self.global_material = MaterialProduct.objects.create(
            name='Global Stock 2x6', input_type=MaterialProduct.InputType.FT,
        )
        self.client.force_login(self.user)

    def test_price_a_global_material_creates_account_scoped_price(self):
        self.client.post(
            reverse('estimating:material-price', args=[self.global_material.pk]),
            {'unit_cost': '6.25'},
        )
        price = MaterialPrice.objects.get(account=self.account, material=self.global_material)
        self.assertEqual(price.unit_cost, Decimal('6.25'))
        # The global material itself is untouched (no account attached to it).
        self.global_material.refresh_from_db()
        self.assertIsNone(self.global_material.account_id)

    def test_blank_price_clears_it(self):
        MaterialPrice.objects.create(account=self.account, material=self.global_material, unit_cost=Decimal('6.25'))
        self.client.post(
            reverse('estimating:material-price', args=[self.global_material.pk]),
            {'unit_cost': ''},
        )
        self.assertFalse(MaterialPrice.objects.filter(account=self.account, material=self.global_material).exists())

    def test_negative_price_rejected(self):
        self.client.post(
            reverse('estimating:material-price', args=[self.global_material.pk]),
            {'unit_cost': '-5'},
        )
        self.assertFalse(MaterialPrice.objects.filter(account=self.account, material=self.global_material).exists())

    def test_library_shows_the_price(self):
        MaterialPrice.objects.create(account=self.account, material=self.global_material, unit_cost=Decimal('6.25'))
        response = self.client.get(reverse('estimating:library'))
        self.assertContains(response, '6.25')
