import io
from pathlib import Path

import fitz
from django.core.files.base import ContentFile
from PIL import Image

from .models import PlanPage

RENDER_ZOOM = 2.0  # ~144 DPI, tune later
THUMBNAIL_WIDTH = 300
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


def rasterize_plan(plan):
    """Split `plan.original_file` into PlanPages: a full-res image plus a
    thumbnail per page. PDFs are rendered page-by-page with PyMuPDF; a plain
    image upload becomes a single PlanPage using the image as-is (re-encoded
    to PNG), avoiding the DPI resampling PyMuPDF would otherwise apply if an
    image were opened as a pseudo-document. Runs synchronously inside the
    request; large PDFs will block it (see docs/CLAUDE.md Open Questions re:
    background processing)."""
    plan.original_file.open('rb')
    try:
        file_bytes = plan.original_file.read()
    finally:
        plan.original_file.close()

    extension = Path(plan.original_file.name).suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return [_save_page(plan, 1, _to_png(file_bytes))]
    return _rasterize_pdf(plan, file_bytes)


def _rasterize_pdf(plan, pdf_bytes):
    matrix = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
    pages = []
    with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
        for page_number, page in enumerate(doc, start=1):
            png_bytes = page.get_pixmap(matrix=matrix).tobytes('png')
            pages.append(_save_page(plan, page_number, png_bytes))
    return pages


def _save_page(plan, page_number, png_bytes):
    thumbnail_bytes = _make_thumbnail(png_bytes)
    file_stub = f'{plan.pk}_{page_number}'
    plan_page = PlanPage(plan=plan, page_number=page_number)
    plan_page.image.save(f'{file_stub}.png', ContentFile(png_bytes), save=False)
    plan_page.thumbnail.save(f'{file_stub}_thumb.png', ContentFile(thumbnail_bytes), save=False)
    plan_page.save()
    return plan_page


def _to_png(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def _make_thumbnail(png_bytes):
    image = Image.open(io.BytesIO(png_bytes))
    image.thumbnail((THUMBNAIL_WIDTH, THUMBNAIL_WIDTH * 4))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()
