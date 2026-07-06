import math
from decimal import Decimal


def pixel_length(geometry):
    """Total Euclidean distance through a Trace's geometry points (a list of
    {'x': .., 'y': ..} dicts). Works for a straight 2-point line today and any
    future multi-point polyline without change."""
    total = 0.0
    for a, b in zip(geometry, geometry[1:]):
        total += math.hypot(b['x'] - a['x'], b['y'] - a['y'])
    return total


def pixel_perimeter(geometry):
    """Perimeter of a closed polygon: the polyline length plus the closing
    edge back to the first point."""
    if len(geometry) < 3:
        return pixel_length(geometry)
    return pixel_length(geometry + [geometry[0]])


def pixel_area(geometry):
    """Area of a simple polygon via the shoelace formula. Point order
    (clockwise vs counterclockwise) doesn't matter - the result is abs()'d."""
    if len(geometry) < 3:
        return 0.0
    total = 0.0
    for a, b in zip(geometry, geometry[1:] + [geometry[0]]):
        total += (a['x'] * b['y']) - (b['x'] * a['y'])
    return abs(total) / 2.0


def bounding_box(geometry):
    """(width_px, height_px) of the axis-aligned bounding box of the points."""
    xs = [p['x'] for p in geometry]
    ys = [p['y'] for p in geometry]
    return (max(xs) - min(xs), max(ys) - min(ys))


def project_point_onto_segment(a, b, p):
    """Perpendicular projection of point p onto segment a-b, with t clamped to
    [0, 1] so every point resolves to a position on the segment. Returns
    {'along_px': Decimal, 'distance_px': Decimal} - along_px is the distance
    from `a` to the projected point (0 at `a`, segment length at `b`);
    distance_px is how far p sits off the segment line itself."""
    ax, ay = Decimal(str(a['x'])), Decimal(str(a['y']))
    bx, by = Decimal(str(b['x'])), Decimal(str(b['y']))
    px, py = Decimal(str(p['x'])), Decimal(str(p['y']))
    dx, dy = bx - ax, by - ay
    length_sq = (dx * dx) + (dy * dy)
    if length_sq <= 0:
        distance_px = Decimal(str(math.sqrt(float((px - ax) ** 2 + (py - ay) ** 2))))
        return {'along_px': Decimal('0'), 'distance_px': distance_px}
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(Decimal('0'), min(Decimal('1'), t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    off_x = px - proj_x
    off_y = py - proj_y
    distance_px = Decimal(str(math.sqrt(float(off_x * off_x + off_y * off_y))))
    along_px = Decimal(str(math.sqrt(float(length_sq)))) * t
    return {'along_px': along_px, 'distance_px': distance_px}


def measure_geometry(tool_type, geometry, scale_pixels_per_foot, settings=None):
    """Convert a Trace's pixel geometry into real-world measurements using the
    PlanPage's calibration. Returns a dict the calculation engine consumes:

    - line / opening: {'length_ft': Decimal}
    - area:           {'area_sqft', 'perimeter_ft', 'bbox_width_ft', 'bbox_height_ft'}
    - polyline:       {'length_ft'} plus area measurements when closed
    - count:          {'count': int} (no calibration required)

    Pure - no DB access."""
    if tool_type == 'count':
        return {'count': len(geometry)}

    scale = Decimal(str(scale_pixels_per_foot))
    settings = settings or {}
    if tool_type == 'area' or (tool_type == 'polyline' and settings.get('closed')):
        width_px, height_px = bounding_box(geometry)
        measurement = {
            'area_sqft': Decimal(str(pixel_area(geometry))) / (scale * scale),
            'perimeter_ft': Decimal(str(pixel_perimeter(geometry))) / scale,
            'bbox_width_ft': Decimal(str(width_px)) / scale,
            'bbox_height_ft': Decimal(str(height_px)) / scale,
        }
        if tool_type == 'polyline':
            measurement['length_ft'] = measurement['perimeter_ft']
        return measurement
    # line and opening are both measured by run length
    return {'length_ft': Decimal(str(pixel_length(geometry))) / scale}
