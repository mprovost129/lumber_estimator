import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from catalog.models import MaterialProduct

User = get_user_model()

CSV_HEADER = 'name,category,species,grade,dimension,input_type,quantity_per_box,lengths,default_length\n'


def csv_upload(body, name='materials.csv'):
    return SimpleUploadedFile(name, (CSV_HEADER + body).encode('utf-8'), content_type='text/csv')


class MaterialImportTests(TestCase):
    """CSV/XLSX supplier list import into the account's own catalog."""

    def setUp(self):
        self.user = User.objects.create_user(email='import@example.com', password='testpass123')
        self.other = User.objects.create_user(email='import-b@example.com', password='testpass123')
        self.url = reverse('estimating:material-import')
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_csv_import_creates_account_materials(self):
        upload = csv_upload(
            'Simpson LUS26X Hanger,connectors,Simpson Strong-Tie,LUS,2x6,each,,,\n'
            'Yard 2x6 KD,Dimensional Lumber,SPF,#2,2x6,ft,,"8;10;12;16",12\n'
            'Yard Screws,fasteners,,,3in,box,350,,\n'
        )
        response = self.client.post(self.url, {'file': upload}, follow=True)
        self.assertRedirects(response, reverse('estimating:library'))
        self.assertContains(response, 'Imported 3 materials')

        hanger = MaterialProduct.objects.get(name='Simpson LUS26X Hanger')
        self.assertEqual(hanger.account_id, self.user.account_id)
        self.assertEqual(hanger.category, 'connectors')
        self.assertEqual(hanger.input_type, 'each')
        self.assertEqual(hanger.normalized_supported_input_types(), [MaterialProduct.InputType.EACH])

        lumber = MaterialProduct.objects.get(name='Yard 2x6 KD')
        # Label form of the category resolves to its key.
        self.assertEqual(lumber.category, 'dimensional')
        lengths = sorted(lumber.lengths.values_list('length_ft', flat=True))
        self.assertEqual([float(length) for length in lengths], [8.0, 10.0, 12.0, 16.0])
        self.assertEqual(lumber.default_length_ft, Decimal('12'))

        screws = MaterialProduct.objects.get(name='Yard Screws')
        self.assertEqual(screws.quantity_per_box, 350)
        self.assertEqual(screws.normalized_supported_input_types(), [MaterialProduct.InputType.BOX])

    def test_reimport_skips_existing_names(self):
        MaterialProduct.objects.create(
            account=self.user.account, name='Already Here', input_type='each',
        )
        upload = csv_upload('Already Here,connectors,,,,each,,,\nBrand New,connectors,,,,each,,,\n')
        response = self.client.post(self.url, {'file': upload}, follow=True)
        self.assertContains(response, 'Imported 1 material')
        self.assertContains(response, 'Skipped 1')
        self.assertEqual(
            MaterialProduct.objects.filter(account=self.user.account, name='Already Here').count(), 1,
        )

    def test_bad_rows_are_reported_and_good_rows_still_import(self):
        upload = csv_upload(
            'Good Item,connectors,,,,each,,,\n'
            'Bad Type,connectors,,,,carton,,,\n'
            'No Lengths,dimensional,,,2x4,ft,,,\n'
        )
        response = self.client.post(self.url, {'file': upload}, follow=True)
        self.assertContains(response, 'Imported 1 material')
        self.assertContains(response, 'input_type must be ft, box, or each')
        self.assertContains(response, 'at least one stock length')
        self.assertFalse(MaterialProduct.objects.filter(name='Bad Type').exists())

    def test_xlsx_import_works(self):
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['name', 'category', 'input_type', 'lengths', 'default_length'])
        sheet.append(['XLSX 2x8', 'dimensional', 'ft', '10;12;16', 16])
        buffer = io.BytesIO()
        workbook.save(buffer)
        upload = SimpleUploadedFile(
            'materials.xlsx', buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response = self.client.post(self.url, {'file': upload}, follow=True)
        self.assertContains(response, 'Imported 1 material')
        product = MaterialProduct.objects.get(name='XLSX 2x8')
        self.assertEqual(product.default_length_ft, Decimal('16'))

    def test_unknown_extension_rejected(self):
        upload = SimpleUploadedFile('materials.txt', b'name\nX', content_type='text/plain')
        response = self.client.post(self.url, {'file': upload})
        self.assertContains(response, 'Upload a .csv or .xlsx file.')
        self.assertFalse(MaterialProduct.objects.filter(name='X').exists())

    def test_import_never_touches_other_accounts(self):
        upload = csv_upload('Mine Only,connectors,,,,each,,,\n')
        self.client.post(self.url, {'file': upload})
        product = MaterialProduct.objects.get(name='Mine Only')
        self.assertEqual(product.account_id, self.user.account_id)
        self.assertNotEqual(product.account_id, self.other.account_id)
