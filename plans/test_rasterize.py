import tempfile

import fitz
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from projects.models import Project

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


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RasterizePlanTests(TestCase):
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
        for index, page in enumerate(pages, start=1):
            self.assertEqual(page.page_number, index)
            self.assertTrue(page.image.name)
            self.assertTrue(page.thumbnail.name)
