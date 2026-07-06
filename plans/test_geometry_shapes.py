"""Tests for polygon area, perimeter, bounding box, and measure_geometry."""
from decimal import Decimal

from .geometry import bounding_box, measure_geometry, pixel_area, pixel_perimeter

RECT = [{'x': 0, 'y': 0}, {'x': 100, 'y': 0}, {'x': 100, 'y': 50}, {'x': 0, 'y': 50}]


def test_pixel_area_rectangle():
    assert pixel_area(RECT) == 5000.0


def test_pixel_area_point_order_does_not_matter():
    assert pixel_area(list(reversed(RECT))) == 5000.0


def test_pixel_perimeter_closes_the_polygon():
    assert pixel_perimeter(RECT) == 300.0


def test_bounding_box():
    assert bounding_box(RECT) == (100, 50)


def test_measure_geometry_line():
    geometry = [{'x': 0, 'y': 0}, {'x': 30, 'y': 40}]  # 50 px
    measurement = measure_geometry('line', geometry, Decimal('10'))
    assert measurement['length_ft'] == Decimal('5')


def test_measure_geometry_area():
    measurement = measure_geometry('area', RECT, Decimal('10'))
    assert measurement['area_sqft'] == Decimal('50')       # 5000 px2 / 100
    assert measurement['perimeter_ft'] == Decimal('30')
    assert measurement['bbox_width_ft'] == Decimal('10')
    assert measurement['bbox_height_ft'] == Decimal('5')


def test_measure_geometry_count_needs_no_scale():
    measurement = measure_geometry('count', [{'x': 1, 'y': 1}, {'x': 2, 'y': 2}], None)
    assert measurement == {'count': 2}


def test_measure_geometry_open_polyline_uses_total_segment_length():
    geometry = [{'x': 0, 'y': 0}, {'x': 30, 'y': 0}, {'x': 30, 'y': 40}]
    measurement = measure_geometry('polyline', geometry, Decimal('10'), {'closed': False})
    assert measurement == {'length_ft': Decimal('7')}


def test_measure_geometry_closed_polyline_includes_area_and_perimeter():
    measurement = measure_geometry('polyline', RECT, Decimal('10'), {'closed': True})
    assert measurement['length_ft'] == Decimal('30')
    assert measurement['perimeter_ft'] == Decimal('30')
    assert measurement['area_sqft'] == Decimal('50')
