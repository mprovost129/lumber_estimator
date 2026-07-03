import io

import fitz
from django.core.files.base import ContentFile
from PIL import Image

from .models import PlanPage

RENDER_ZOOM = 2.0  # ~144 DPI, tune later
THUMBNAIL_WIDTH = 300


def rasterize_plan(plan):
    """Split `plan.original_file` (a PDF) into PlanPages: a full-res image
    plus a thumbnail per page. Runs synchronously inside the request; large
    PDFs will block it (see docs/CLAUDE.md Open Questions re: background
    processing)."""
    plan.original_file.open('rb')
    try:
        pdf_bytes = plan.original_file.read()
    finally:
        plan.original_file.close()

    matrix = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
    pages = []
    with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
        for page_number, page in enumerate(doc, start=1):
            png_bytes = page.get_pixmap(matrix=matrix).tobytes('png')
            thumbnail_bytes = _make_thumbnail(png_bytes)

            file_stub = f'{plan.pk}_{page_number}'
            plan_page = PlanPage(plan=plan, page_number=page_number)
            plan_page.image.save(f'{file_stub}.png', ContentFile(png_bytes), save=False)
            plan_page.thumbnail.save(f'{file_stub}_thumb.png', ContentFile(thumbnail_bytes), save=False)
            plan_page.save()
            pages.append(plan_page)

    return pages


def _make_thumbnail(png_bytes):
    image = Image.open(io.BytesIO(png_bytes))
    image.thumbnail((THUMBNAIL_WIDTH, THUMBNAIL_WIDTH * 4))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()
