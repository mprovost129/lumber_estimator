from django.test import TestCase

from .geometry import pixel_length


class PixelLengthTests(TestCase):
    def test_horizontal_line(self):
        geometry = [{'x': 0, 'y': 0}, {'x': 300, 'y': 0}]
        self.assertEqual(pixel_length(geometry), 300.0)

    def test_diagonal_line(self):
        geometry = [{'x': 0, 'y': 0}, {'x': 3, 'y': 4}]
        self.assertEqual(pixel_length(geometry), 5.0)

    def test_multi_point_polyline_sums_segments(self):
        geometry = [{'x': 0, 'y': 0}, {'x': 10, 'y': 0}, {'x': 10, 'y': 10}]
        self.assertEqual(pixel_length(geometry), 20.0)

    def test_single_point_has_zero_length(self):
        self.assertEqual(pixel_length([{'x': 5, 'y': 5}]), 0.0)
