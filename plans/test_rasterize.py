import io
import tempfile

import fitz
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from projects.models import Project

from .forms import PlanUploadForm
from .models import Plan, PlanPage
from .services import rasterize_plan

User = get_user_model()


def build_test_pdf(num_pages=1):
    doc = fitz.open()
    for _ in range(num_pages):
        doc.new_page(width=200, height=200)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def build_test_png(width=100, height=150):
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), color='red').save(buffer, format='PNG')
    return buffer.getvalue()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RasterizePlanTests(TestCase):
    def _assert_valid_page(self, page, expected_number):
        self.assertEqual(page.page_number, expected_number)
        self.assertTrue(page.image.name)
        self.assertTrue(page.thumbnail.name)

    def test_rasterize_plan_creates_one_page_per_pdf_page(self):
        user = User.objects.create_user(email='raster@example.com', password='testpass123')
        project = Project.objects.create(account=user.account, name='Raster House')
        plan = Plan.objects.create(
            project=project,
            original_file=SimpleUploadedFile('test.pdf', build_test_pdf(num_pages=2), content_type='application/pdf'),
        )

        pages = rasterize_plan(plan)

        self.assertEqual(len(pages), 2)
        self.assertEqual(PlanPage.objects.filter(plan=plan).count(), 2)
        self._assert_valid_page(pages[0], expected_number=1)
        self._assert_valid_page(pages[1], expected_number=2)

    def test_rasterize_plan_handles_a_plain_image_upload(self):
        user = User.objects.create_user(email='raster-img@example.com', password='testpass123')
        project = Project.objects.create(account=user.account, name='Raster Image House')
        plan = Plan.objects.create(
            project=project,
            original_file=SimpleUploadedFile('site-photo.jpg', build_test_png(), content_type='image/jpeg'),
        )

        pages = rasterize_plan(plan)

        self.assertEqual(len(pages), 1)
        self._assert_valid_page(pages[0], expected_number=1)

    def test_rasterized_image_preserves_native_resolution(self):
        user = User.objects.create_user(email='raster-res@example.com', password='testpass123')
        project = Project.objects.create(account=user.account, name='Raster Res House')
        plan = Plan.objects.create(
            project=project,
            original_file=SimpleUploadedFile('scan.png', build_test_png(400, 600), content_type='image/png'),
        )

        pages = rasterize_plan(plan)

        with Image.open(pages[0].image) as saved_image:
            self.assertEqual(saved_image.size, (400, 600))


class PlanUploadFormTests(TestCase):
    def _assert_extension_accepted(self, filename, content_type):
        form = PlanUploadForm(files={
            'original_file': SimpleUploadedFile(filename, b'fake-bytes', content_type=content_type),
        })
        self.assertTrue(form.is_valid(), f'{filename} should be accepted: {form.errors}')

    def test_rejects_unsupported_file_types(self):
        form = PlanUploadForm(files={
            'original_file': SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain'),
        })
        self.assertFalse(form.is_valid())

    def test_accepts_pdf(self):
        self._assert_extension_accepted('plan.pdf', 'application/pdf')

    def test_accepts_png(self):
        self._assert_extension_accepted('plan.png', 'image/png')

    def test_accepts_jpg(self):
        self._assert_extension_accepted('plan.jpg', 'image/jpeg')

    def test_accepts_jpeg(self):
        self._assert_extension_accepted('plan.jpeg', 'image/jpeg')
