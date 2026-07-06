"""Procedural framing previews for intelligent wall traces.

This module intentionally does not persist studs/plates/headers. It builds a
read-only wall elevation model from an existing Trace, its settings snapshot,
the page calibration, and nearby opening traces. Later editable member overrides
can be layered on top of this generated model.
"""
import math
from decimal import Decimal

from .geometry import measure_geometry, pixel_length, project_point_onto_segment
from .models import Trace

DEFAULT_WALL_HEIGHT_IN = 108
DEFAULT_STUD_SPACING_IN = 16
DEFAULT_WINDOW_SILL_IN = 36
DEFAULT_WINDOW_HEIGHT_IN = 48
DEFAULT_DOOR_HEIGHT_IN = 80
DEFAULT_HEADER_DEPTH_IN = 9.25
DEFAULT_WALL_THICKNESS_IN = 5.5
# Standard double top plate (2 x 1.5") + single bottom plate (1 x 1.5") - the
# amount subtracted from overall wall height to get the actual stud cut
# length, e.g. a 97-1/8" wall (8'-1-1/8") needs a 92-5/8" precut stud.
# estimating.calculations imports this too, so a wall's stud LineItem picks
# the same cut length this elevation preview draws. Doesn't yet vary with a
# custom top/bottom plate count - both this module and estimating.calculations
# share that limitation identically, so their stud lengths can't drift apart.
STANDARD_PLATE_ALLOWANCE_IN = Decimal('4.5')


def build_wall_elevation(trace):
    """Return a generated wall-elevation model for a line/polyline wall Trace."""
    if trace.tool_type not in {Trace.ToolType.LINE, Trace.ToolType.POLYLINE}:
        raise ValueError('Wall elevation is only available for line or polyline wall traces.')
    if trace.plan_page.scale_pixels_per_foot is None:
        raise ValueError('Calibrate this page before viewing a wall elevation.')

    settings = trace.settings or {}
    wall_height_in = int(settings.get('wall_height_in') or DEFAULT_WALL_HEIGHT_IN)
    stud_spacing_in = int(settings.get('stud_spacing_in') or DEFAULT_STUD_SPACING_IN)
    measurement = measure_geometry(
        trace.tool_type,
        trace.geometry,
        trace.plan_page.scale_pixels_per_foot,
        settings,
    )
    length_ft = Decimal(str(measurement['length_ft']))
    length_in = float(length_ft * 12)
    height_in = float(wall_height_in)

    openings = _attached_openings(trace)
    top_plate_count = int(settings.get('top_plate_count') or 2)
    bottom_plate_count = int(settings.get('bottom_plate_count') or 1)
    wall_thickness_in = float(settings.get('wall_thickness_in') or DEFAULT_WALL_THICKNESS_IN)

    members = []
    members.extend(_plate_members(length_in, height_in, top_plate_count, bottom_plate_count))
    members.extend(_stud_members(length_in, height_in, stud_spacing_in, openings))
    for opening in openings:
        members.extend(_opening_members(opening, height_in))
    members = _apply_member_overrides(members, settings)

    return {
        'trace_id': trace.id,
        'assembly_name': trace.assembly.name if trace.assembly_id else None,
        'material_name': trace.material.name if trace.material_id else None,
        'length_ft': round(float(length_ft), 3),
        'length_in': round(length_in, 3),
        'height_in': wall_height_in,
        'stud_spacing_in': stud_spacing_in,
        'top_plate_count': top_plate_count,
        'bottom_plate_count': bottom_plate_count,
        'wall_thickness_in': wall_thickness_in,
        'openings': openings,
        'members': members,
        'member_overrides': settings.get('wall_member_overrides') or {},
        'layers': _wall_layers(settings, wall_thickness_in),
        'cut_list': _cut_list(members),
        'summary': _summary(members, openings),
        'notes': [
            'Generated from the wall trace and nearby opening traces on this plan page.',
            'Members are procedural preview objects; individual stud/plate overrides are not persisted yet.',
        ],
    }


def _plate_members(length_in, height_in, top_plate_count=2, bottom_plate_count=1):
    members = []
    for i in range(bottom_plate_count):
        members.append(_member(f'bottom_plate_{i + 1}', 'Bottom plate', 0, i * 1.5, length_in, 1.5))
    for i in range(top_plate_count):
        y = height_in - ((top_plate_count - i) * 1.5)
        members.append(_member(f'top_plate_{i + 1}', 'Top plate', 0, y, length_in, 1.5))
    return members


def _stud_members(length_in, height_in, spacing_in, openings):
    members = []
    stud_height_in = height_in - float(STANDARD_PLATE_ALLOWANCE_IN)
    x = 0
    i = 0
    while x <= length_in + 0.01:
        if not _inside_opening(x, openings):
            members.append(_member(f'stud_{i}', 'Stud', x - 0.75, 1.5, 1.5, stud_height_in))
        i += 1
        x = i * spacing_in
    if not any(abs(m['x'] - (length_in - 0.75)) < 0.01 for m in members):
        members.append(_member('end_stud', 'End stud', length_in - 1.5, 1.5, 1.5, height_in - 4.5))
    return members


def _opening_members(opening, height_in):
    left = opening['left_in']
    right = opening['right_in']
    bottom = opening['sill_height_in']
    top = opening['top_in']
    header_depth = opening['header_depth_in']
    header_y = min(height_in - 4.5 - header_depth, top)
    members = [
        _member(f"opening_{opening['id']}_king_l", 'King stud', left - 3, 1.5, 1.5, height_in - 4.5),
        _member(f"opening_{opening['id']}_king_r", 'King stud', right + 1.5, 1.5, 1.5, height_in - 4.5),
        _member(f"opening_{opening['id']}_jack_l", 'Jack stud', left - 1.5, 1.5, 1.5, max(0, header_y - 1.5)),
        _member(f"opening_{opening['id']}_jack_r", 'Jack stud', right, 1.5, 1.5, max(0, header_y - 1.5)),
        _member(f"opening_{opening['id']}_header", 'Header', left - 1.5, header_y, (right - left) + 3, header_depth),
    ]
    if opening['opening_type'] == 'window':
        members.append(_member(f"opening_{opening['id']}_sill", 'Rough sill', left, bottom, right - left, 1.5))
        cripple_count = max(1, math.floor((right - left) / max(opening['stud_spacing_in'], 1)))
        for i in range(cripple_count + 1):
            x = left + min(i * opening['stud_spacing_in'], right - left)
            members.append(_member(f"opening_{opening['id']}_cripple_sill_{i}", 'Sill cripple', x - 0.75, 1.5, 1.5, max(0, bottom - 1.5)))
            members.append(_member(f"opening_{opening['id']}_cripple_header_{i}", 'Header cripple', x - 0.75, header_y + header_depth, 1.5, max(0, height_in - (header_y + header_depth) - 3)))
    return members


def _attached_openings(trace):
    """Openings explicitly attached to this wall (Trace.parent_wall), with
    each one's position along the wall found by projecting its geometry onto
    whichever wall segment it's closest to (works for a straight 2-point line
    and a multi-segment polyline alike, with "along the wall" measured
    cumulatively from the wall's start). Attachment itself is no longer a
    proximity guess - it's an explicit choice made in the inspector panel -
    so every attached opening is included even if its own geometry doesn't
    sit exactly on the wall line; the projection is clamped to the nearest
    point on the wall path rather than rejected."""
    if trace.tool_type not in {Trace.ToolType.LINE, Trace.ToolType.POLYLINE} or len(trace.geometry) < 2:
        return []

    scale = Decimal(str(trace.plan_page.scale_pixels_per_foot))
    segments = list(zip(trace.geometry, trace.geometry[1:]))

    cumulative_px = Decimal('0')
    segment_offsets = []
    for a, b in segments:
        segment_offsets.append(cumulative_px)
        cumulative_px += Decimal(str(pixel_length([a, b])))
    if cumulative_px <= 0:
        return []

    openings = []
    for opening in trace.attached_openings.filter(tool_type=Trace.ToolType.OPENING):
        points = opening.geometry or []
        if len(points) < 2:
            continue
        best = None
        for (a, b), offset_px in zip(segments, segment_offsets):
            p1 = project_point_onto_segment(a, b, points[0])
            p2 = project_point_onto_segment(a, b, points[1])
            distance_px = max(p1['distance_px'], p2['distance_px'])
            if best is None or distance_px < best['distance_px']:
                best = {
                    'distance_px': distance_px,
                    'left_px': offset_px + min(p1['along_px'], p2['along_px']),
                    'right_px': offset_px + max(p1['along_px'], p2['along_px']),
                }
        left_ft = best['left_px'] / scale
        right_ft = best['right_px'] / scale
        if right_ft <= left_ft:
            continue
        settings = opening.settings or {}
        opening_type = settings.get('opening_type') or 'window'
        sill_height_in = int(settings.get('sill_height_in') or (0 if opening_type == 'door' else DEFAULT_WINDOW_SILL_IN))
        rough_height_in = int(settings.get('rough_height_in') or (DEFAULT_DOOR_HEIGHT_IN if opening_type == 'door' else DEFAULT_WINDOW_HEIGHT_IN))
        stud_spacing_in = int(settings.get('stud_spacing_in') or DEFAULT_STUD_SPACING_IN)
        label = settings.get('label') or ('Door' if opening_type == 'door' else 'Window')
        openings.append({
            'id': opening.id,
            'opening_type': opening_type,
            'label': label,
            'left_in': round(float(left_ft * 12), 3),
            'right_in': round(float(right_ft * 12), 3),
            'width_in': round(float((right_ft - left_ft) * 12), 3),
            'sill_height_in': sill_height_in,
            'rough_height_in': rough_height_in,
            'top_in': sill_height_in + rough_height_in,
            'header_depth_in': float(settings.get('header_depth_in') or DEFAULT_HEADER_DEPTH_IN),
            'stud_spacing_in': stud_spacing_in,
        })
    return sorted(openings, key=lambda item: item['left_in'])


def _inside_opening(x, openings):
    return any((opening['left_in'] - 1.5) < x < (opening['right_in'] + 1.5) for opening in openings)


def _member(member_id, role, x, y, width, height, source='generated'):
    return {
        'id': str(member_id),
        'role': role,
        'x': round(float(x), 3),
        'y': round(float(y), 3),
        'width': round(float(width), 3),
        'height': round(float(height), 3),
        'source': source,
    }


def validate_wall_member_overrides(overrides):
    """Raise ValueError if `overrides` isn't shaped the way `_apply_member_overrides`
    expects. Called at the point a client tries to persist settings (TraceCreateView/
    TraceUpdateView) so malformed data is rejected with a clear 400 instead of
    being silently dropped later when the wall elevation is generated."""
    if overrides is None:
        return
    if not isinstance(overrides, dict):
        raise ValueError('wall_member_overrides must be an object.')

    deleted = overrides.get('deleted', [])
    if not isinstance(deleted, list) or not all(isinstance(item, (str, int)) for item in deleted):
        raise ValueError('wall_member_overrides.deleted must be a list of member ids.')

    edited = overrides.get('edited', {})
    if not isinstance(edited, dict):
        raise ValueError('wall_member_overrides.edited must be an object keyed by member id.')
    for member_id, changes in edited.items():
        if not isinstance(changes, dict):
            raise ValueError(f'wall_member_overrides.edited["{member_id}"] must be an object.')
        for key in ('x', 'y', 'width', 'height'):
            if key in changes and changes[key] is not None:
                try:
                    float(changes[key])
                except (TypeError, ValueError):
                    raise ValueError(
                        f'wall_member_overrides.edited["{member_id}"].{key} must be a number.',
                    ) from None

    added = overrides.get('added', [])
    if not isinstance(added, list):
        raise ValueError('wall_member_overrides.added must be a list.')
    for index, custom in enumerate(added):
        if not isinstance(custom, dict):
            raise ValueError(f'wall_member_overrides.added[{index}] must be an object.')
        for key in ('x', 'y', 'width', 'height'):
            if key in custom and custom[key] is not None:
                try:
                    float(custom[key])
                except (TypeError, ValueError):
                    raise ValueError(
                        f'wall_member_overrides.added[{index}].{key} must be a number.',
                    ) from None


def _apply_member_overrides(members, settings):
    """Apply lightweight persisted framing edits to generated members.

    The wall stays procedural, but user edits are stored as compact overrides in
    trace.settings['wall_member_overrides']:
      - edited: map of member id -> x/y/width/height/role changes
      - deleted: list of generated member ids hidden from the model
      - added: list of fully custom member dictionaries

    Defensive on read: malformed overrides (e.g. saved before validation existed)
    are skipped rather than raised, since a bad override should never break
    viewing the wall. Persisting bad data in the first place is what
    validate_wall_member_overrides() guards against.
    """
    overrides = settings.get('wall_member_overrides')
    if not isinstance(overrides, dict):
        return list(members)

    deleted = set()
    for item in overrides.get('deleted') or []:
        deleted.add(str(item))

    edited = overrides.get('edited')
    edited = edited if isinstance(edited, dict) else {}

    output = []
    for member in members:
        member_id = str(member['id'])
        if member_id in deleted:
            continue
        updated = dict(member)
        changes = edited.get(member_id)
        changes = changes if isinstance(changes, dict) else {}
        for key in ('x', 'y', 'width', 'height'):
            if key in changes and changes[key] is not None:
                try:
                    updated[key] = round(float(changes[key]), 3)
                except (TypeError, ValueError):
                    continue
        if changes.get('role'):
            updated['role'] = str(changes['role'])
        if changes:
            updated['source'] = 'edited'
        output.append(updated)

    added = overrides.get('added')
    for index, custom in enumerate(added if isinstance(added, list) else []):
        if not isinstance(custom, dict):
            continue
        try:
            output.append(_member(
                custom.get('id') or f'custom_{index + 1}',
                custom.get('role') or 'Custom member',
                custom.get('x') or 0,
                custom.get('y') or 0,
                custom.get('width') or 1.5,
                custom.get('height') or 96,
                source='custom',
            ))
        except (TypeError, ValueError):
            continue
    return output


def _wall_layers(settings, wall_thickness_in):
    """Return conceptual wall layers for a future 3D/material view."""
    layers = [
        {'key': 'framing', 'label': settings.get('framing_label') or 'Framing cavity', 'thickness_in': wall_thickness_in, 'visible': True},
    ]
    if settings.get('interior_drywall', True):
        layers.insert(0, {'key': 'drywall', 'label': 'Interior drywall', 'thickness_in': 0.5, 'visible': True})
    if settings.get('exterior_sheathing', True):
        layers.append({'key': 'sheathing', 'label': 'Exterior sheathing', 'thickness_in': 0.5, 'visible': True})
    if settings.get('house_wrap', True):
        layers.append({'key': 'wrap', 'label': 'House wrap / WRB', 'thickness_in': 0.05, 'visible': True})
    if settings.get('siding', True):
        layers.append({'key': 'siding', 'label': 'Siding / finish', 'thickness_in': 0.75, 'visible': True})
    offset = 0
    for layer in layers:
        layer['offset_in'] = round(offset, 3)
        offset += float(layer['thickness_in'])
    return layers


def _cut_list(members):
    """Group generated framing members into a practical preview cut list."""
    grouped = {}
    for member in members:
        length = max(member['width'], member['height'])
        key = (member['role'], round(length, 1))
        grouped[key] = grouped.get(key, 0) + 1
    rows = []
    for (role, length_in), qty in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        rows.append({
            'role': role,
            'quantity': qty,
            'length_in': length_in,
            'length_ft': round(length_in / 12, 2),
        })
    return rows

def _summary(members, openings):
    roles = {}
    for member in members:
        roles[member['role']] = roles.get(member['role'], 0) + 1
    return {
        'member_count': len(members),
        'opening_count': len(openings),
        'roles': roles,
    }
