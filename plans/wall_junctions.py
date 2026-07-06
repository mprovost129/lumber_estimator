"""Detects geometric junctions between wall traces - a polyline bending, two
separate walls meeting at a shared endpoint (a corner), and one wall's
endpoint landing on another wall's span (a T-intersection) - so the calc
engine can add the extra studs real framing requires at each kind of
junction. Pure, read-only geometry; nothing here persists anything.

All distance/tolerance comparisons are done in Decimal (matching
plans.geometry's convention) to avoid mixing with plain float math.
"""
import math
from decimal import Decimal

from .geometry import project_point_onto_segment
from .models import Trace

# A hand-drawn trace rarely lands pixel-perfect on another one; anything
# closer than this (in real feet - converted per-page via its own
# calibration, so the tolerance means the same thing at any drawing scale)
# counts as "meeting."
JUNCTION_TOLERANCE_FT = Decimal('0.5')

# Below this sine-of-angle threshold, two adjacent direction vectors are
# treated as collinear (no real corner) - absorbs floating-point noise and a
# few redundant clicks along an otherwise-straight run.
BEND_SINE_EPSILON = 0.01


def _wall_traces_on_page(plan_page_id, exclude_pk=None):
    qs = Trace.objects.filter(
        plan_page_id=plan_page_id, tool_type__in=[Trace.ToolType.LINE, Trace.ToolType.POLYLINE],
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return list(qs)


def _is_real_bend(v1, v2):
    """True if two direction vectors are NOT collinear (in either the same or
    opposite direction) - i.e. there's a genuine angle between them, beyond
    BEND_SINE_EPSILON. Used both for a polyline's own internal bends and for
    whether two walls meeting at a shared endpoint actually change direction
    there (a corner) or just continue straight through (not a corner)."""
    v1x, v1y = v1
    v2x, v2y = v2
    len1 = math.hypot(v1x, v1y)
    len2 = math.hypot(v2x, v2y)
    if len1 < 1e-6 or len2 < 1e-6:
        return False
    cross = v1x * v2y - v1y * v2x
    sine = abs(cross) / (len1 * len2)
    return sine > BEND_SINE_EPSILON


def _internal_bend_count(geometry):
    """Number of interior polyline vertices where the wall actually changes
    direction, skipping redundant collinear points."""
    count = 0
    for i in range(1, len(geometry) - 1):
        a, b, c = geometry[i - 1], geometry[i], geometry[i + 1]
        v1 = (b['x'] - a['x'], b['y'] - a['y'])
        v2 = (c['x'] - b['x'], c['y'] - b['y'])
        if _is_real_bend(v1, v2):
            count += 1
    return count


def _direction_into_wall(wall, at_start):
    """Vector from the given endpoint toward the wall's interior - used to
    test whether two walls meeting at a shared point genuinely change
    direction there (a corner) or continue straight through (not a corner,
    e.g. one long wall split into two trace segments)."""
    if at_start:
        a, b = wall.geometry[0], wall.geometry[1]
    else:
        a, b = wall.geometry[-1], wall.geometry[-2]
    return (b['x'] - a['x'], b['y'] - a['y'])


def _points_close(p1, p2, tolerance_px):
    dx = Decimal(str(p1['x'])) - Decimal(str(p2['x']))
    dy = Decimal(str(p1['y'])) - Decimal(str(p2['y']))
    distance_px = Decimal(str(math.sqrt(float(dx * dx + dy * dy))))
    return distance_px <= tolerance_px


def _shares_a_corner(point, my_direction, other_wall, tolerance_px):
    """True if `point` (one of this wall's own endpoints, with `my_direction`
    its direction into this wall's interior at that point) meets
    `other_wall` at a genuine corner: either matching one of its overall
    endpoints at a real angle (not a straight-through continuation - the
    collinearity check that keeps a straight wall split into two trace
    segments from being falsely flagged as a corner), or landing on one of
    its own internal bend vertices (always treated as a corner there - a
    narrower, rarer case where checking against that vertex's two adjacent
    segments isn't worth the added complexity)."""
    vertices = other_wall.geometry
    for index, vertex in enumerate(vertices):
        if not _points_close(point, vertex, tolerance_px):
            continue
        if index == 0 or index == len(vertices) - 1:
            other_direction = _direction_into_wall(other_wall, at_start=(index == 0))
            if _is_real_bend(my_direction, other_direction):
                return True
            continue  # collinear continuation here; keep checking other vertices
        return True  # internal vertex match - always a corner
    return False


def _lands_on_span(point, wall, tolerance_px):
    """True if `point` projects onto one of `wall`'s segments at a position
    strictly inside that segment (not within tolerance of either end - that's
    a vertex match, handled by _shares_a_corner instead) and within
    tolerance_px perpendicular distance of the wall line."""
    for a, b in zip(wall.geometry, wall.geometry[1:]):
        segment_length_px = math.hypot(b['x'] - a['x'], b['y'] - a['y'])
        if segment_length_px <= 0:
            continue
        result = project_point_onto_segment(a, b, point)
        segment_length_dec = Decimal(str(segment_length_px))
        along = result['along_px']
        if along <= tolerance_px or (segment_length_dec - along) <= tolerance_px:
            continue
        if result['distance_px'] <= tolerance_px:
            return True
    return False


def detect_wall_junctions(trace):
    """{'corner_count', 'partition_t_count', 'through_t_count'} for `trace` -
    how many corner- and T-intersection-type junctions it participates in,
    from its own polyline bends plus its geometric relationship to every
    other line/polyline trace on the same PlanPage. All zero if the trace
    isn't a wall, has fewer than 2 points, or the page isn't calibrated.

    corner_count: this wall's own real polyline bends (each counted TWICE -
    a bend stands in for both "a wall ending" and "a wall starting" at that
    point, matching two separate wall traces meeting there, where each one
    independently contributes its own single occurrence) plus one occurrence
    per own endpoint that meets another wall at a genuine angle (never more
    than one per endpoint, regardless of how many other walls converge there
    - so a 3+-way junction isn't multiply counted from any single wall's own
    perspective).

    partition_t_count: one occurrence per own endpoint that lands on
    another wall's span instead of meeting it at a corner - this wall is the
    partition whose end butts into a through-wall.

    through_t_count: one occurrence per *other* wall's endpoint that lands
    on this wall's own span - this wall is the through-wall needing a
    backer/nailer stud for each partition butting into it.
    """
    empty = {'corner_count': 0, 'partition_t_count': 0, 'through_t_count': 0}
    if trace.tool_type not in (Trace.ToolType.LINE, Trace.ToolType.POLYLINE) or len(trace.geometry) < 2:
        return empty
    scale = trace.plan_page.scale_pixels_per_foot
    if scale is None:
        return empty
    tolerance_px = JUNCTION_TOLERANCE_FT * Decimal(str(scale))

    corner_count = 2 * _internal_bend_count(trace.geometry)
    partition_t_count = 0
    other_walls = _wall_traces_on_page(trace.plan_page_id, exclude_pk=trace.pk)

    for at_start in (True, False):
        endpoint = trace.geometry[0] if at_start else trace.geometry[-1]
        my_direction = _direction_into_wall(trace, at_start=at_start)
        if any(_shares_a_corner(endpoint, my_direction, other, tolerance_px) for other in other_walls):
            corner_count += 1
        elif any(_lands_on_span(endpoint, other, tolerance_px) for other in other_walls):
            partition_t_count += 1

    through_t_count = 0
    for other in other_walls:
        if len(other.geometry) < 2:
            continue
        for other_at_start in (True, False):
            other_endpoint = other.geometry[0] if other_at_start else other.geometry[-1]
            other_direction = _direction_into_wall(other, at_start=other_at_start)
            if _shares_a_corner(other_endpoint, other_direction, trace, tolerance_px):
                continue  # already an endpoint-to-endpoint corner from the other wall's side
            if _lands_on_span(other_endpoint, trace, tolerance_px):
                through_t_count += 1

    return {
        'corner_count': corner_count,
        'partition_t_count': partition_t_count,
        'through_t_count': through_t_count,
    }


def could_share_a_junction(trace_a, trace_b):
    """Cheap pre-filter: could `trace_a` and `trace_b` possibly share a
    corner or T-intersection? True if either wall has an endpoint within a
    generous margin of the other's geometry. Used to skip a full
    detect_wall_junctions() recompute for siblings that are obviously too far
    away to be affected by a wall being created or deleted nearby - both
    traces must be on an already-calibrated page (returns False otherwise,
    same as detect_wall_junctions)."""
    if len(trace_a.geometry) < 2 or len(trace_b.geometry) < 2:
        return False
    scale = trace_a.plan_page.scale_pixels_per_foot
    if scale is None:
        return False
    tolerance_px = JUNCTION_TOLERANCE_FT * Decimal(str(scale))

    for point in (trace_a.geometry[0], trace_a.geometry[-1]):
        if any(_points_close(point, vertex, tolerance_px) for vertex in trace_b.geometry):
            return True
        if _lands_on_span(point, trace_b, tolerance_px):
            return True
    for point in (trace_b.geometry[0], trace_b.geometry[-1]):
        if _lands_on_span(point, trace_a, tolerance_px):
            return True
    return False
