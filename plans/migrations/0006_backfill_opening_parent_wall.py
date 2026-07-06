import math
from decimal import Decimal

from django.db import migrations

OPENING_SNAP_TOLERANCE_FT = Decimal('2.0')


def _project_point(a, b, p):
    ax, ay = Decimal(str(a['x'])), Decimal(str(a['y']))
    bx, by = Decimal(str(b['x'])), Decimal(str(b['y']))
    px, py = Decimal(str(p['x'])), Decimal(str(p['y']))
    dx, dy = bx - ax, by - ay
    length_sq = (dx * dx) + (dy * dy)
    if length_sq <= 0:
        return None
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    if t < 0 or t > 1:
        return None
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    off_x = px - proj_x
    off_y = py - proj_y
    distance_px = Decimal(str(math.sqrt(float(off_x * off_x + off_y * off_y))))
    return distance_px


def _best_distance_for_wall(wall_geometry, opening_points):
    """Smallest projected distance (px) of `opening_points` onto any segment
    of `wall_geometry`, or None if it doesn't project onto any segment."""
    if len(wall_geometry) < 2 or len(opening_points) < 2:
        return None
    best_distance = None
    for a, b in zip(wall_geometry, wall_geometry[1:]):
        d1 = _project_point(a, b, opening_points[0])
        d2 = _project_point(a, b, opening_points[1])
        if d1 is None or d2 is None:
            continue
        distance_px = max(d1, d2)
        if best_distance is None or distance_px < best_distance:
            best_distance = distance_px
    return best_distance


def backfill_parent_wall(apps, schema_editor):
    """Reproduce today's proximity-based wall-elevation preview as an explicit
    parent_wall assignment, so existing plans don't visually change. Logic is
    ported inline (not imported from plans/framing.py) since migrations must
    remain runnable against old app code forever, even after framing.py
    changes. Unlike the old per-wall heuristic (each wall independently
    decided which openings looked "nearby"), an opening can only have one
    parent here - if it was ambiguously close to more than one wall before,
    it's assigned to whichever it's physically closest to."""
    Trace = apps.get_model('plans', 'Trace')

    for opening in Trace.objects.filter(tool_type='opening').select_related('plan_page'):
        page = opening.plan_page
        if page.scale_pixels_per_foot is None:
            continue
        tolerance_px = OPENING_SNAP_TOLERANCE_FT * Decimal(str(page.scale_pixels_per_foot))

        best_wall = None
        best_distance = None
        walls = Trace.objects.filter(
            plan_page=page, tool_type__in=['line', 'polyline'],
        ).exclude(pk=opening.pk)
        for wall in walls:
            distance_px = _best_distance_for_wall(wall.geometry or [], opening.geometry or [])
            if distance_px is None:
                continue
            if best_distance is None or distance_px < best_distance:
                best_distance = distance_px
                best_wall = wall

        if best_wall is not None and best_distance is not None and best_distance <= tolerance_px:
            opening.parent_wall = best_wall
            opening.save(update_fields=['parent_wall'])


def unset_parent_wall(apps, schema_editor):
    Trace = apps.get_model('plans', 'Trace')
    Trace.objects.filter(tool_type='opening').update(parent_wall=None)


class Migration(migrations.Migration):

    dependencies = [
        ('plans', '0005_trace_parent_wall'),
    ]

    operations = [
        migrations.RunPython(backfill_parent_wall, unset_parent_wall),
    ]
