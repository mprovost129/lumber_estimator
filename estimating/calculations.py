"""Calculation engine: converts a Trace's measurement into LineItem quantities
via an Assembly's CalculationRules. All formulas are the fixed, parameterized
kinds in CalculationRule.FormulaKind - not a free-form expression language.

A `measurement` is the dict produced by plans.geometry.measure_geometry():
    line / opening: {'length_ft': Decimal}
    area:           {'area_sqft', 'perimeter_ft', 'bbox_width_ft', 'bbox_height_ft'}
    count:          {'count': int}
"""
import math
from decimal import Decimal

from catalog.models import MaterialProduct
from plans.framing import STANDARD_PLATE_ALLOWANCE_IN
from plans.geometry import measure_geometry
from plans.models import Trace
from plans.wall_junctions import detect_wall_junctions

from .models import CalculationRule, LineItem

NO_JUNCTIONS = {'corner_count': 0, 'partition_t_count': 0, 'through_t_count': 0}

HEADER_BEARING_FT = Decimal('0.25')  # 3" total bearing added to an opening's width

Kind = CalculationRule.FormulaKind


def _spacing_in(settings, default=16):
    """Member spacing in inches, from the Trace's settings snapshot. Line
    tools write `stud_spacing_in`; area tools write `spacing_in`."""
    return Decimal(str(settings.get('spacing_in') or settings.get('stud_spacing_in') or default))


def _stock_length_or_none(material, required_ft):
    """Smallest stock length covering `required_ft` for FT materials; None for
    each/box materials (e.g. trusses ordered per unit)."""
    if material.input_type != MaterialProduct.InputType.FT:
        return None
    return material.stock_length_for(required_ft)


def _spliced_pieces(material, required_ft):
    """(piece_count, piece_length_or_None) to build one member of `required_ft`,
    splicing from stock when it is longer than the longest stock piece. For
    each/box materials there are no stock lengths, so it is always one unit."""
    if material.input_type != MaterialProduct.InputType.FT:
        return 1, None
    return material.pieces_for_length(required_ft)


def _primary_measurement_value(measurement):
    """Whichever of length_ft / area_sqft / count is present, for formula kinds
    (like PER_BOX) that apply regardless of which tool produced the trace."""
    for key in ('length_ft', 'area_sqft', 'count'):
        if key in measurement:
            return Decimal(str(measurement[key]))
    raise ValueError('No usable measurement (length_ft/area_sqft/count) for this rule.')


def _area_members(measurement, settings):
    """(run_ft, member_length_ft) for PER_AREA_SPACING. `member_direction`
    says which way the members RUN across the traced rectangle's bounding box:
    'horizontal' members are as long as the bbox width and are spaced up the
    bbox height; 'vertical' is the reverse."""
    direction = settings.get('member_direction') or 'horizontal'
    if direction == 'vertical':
        return measurement['bbox_width_ft'], measurement['bbox_height_ft']
    return measurement['bbox_height_ft'], measurement['bbox_width_ft']


def _attached_opening_width_ft(trace):
    """Total width of openings (windows/doors) cut into a wall trace. Used to
    keep the wall's own stud count from double-counting studs where an
    opening's king/jack/cripple studs (generated separately, from the
    opening's own assembly) take over instead. Plates are deliberately left
    alone - top plates run continuously over openings in standard framing,
    and the reference workbook's Wall Takeoff formulas don't discount them
    either, so this only feeds into PER_SPACING (studs)."""
    if trace is None or trace.tool_type not in (Trace.ToolType.LINE, Trace.ToolType.POLYLINE):
        return Decimal('0')
    scale = trace.plan_page.scale_pixels_per_foot
    if scale is None:
        return Decimal('0')
    total = Decimal('0')
    for opening in trace.attached_openings.all():
        measurement = measure_geometry(opening.tool_type, opening.geometry, scale, opening.settings)
        total += measurement.get('length_ft', Decimal('0'))
    return total


def evaluate_rule(rule, measurement, settings, opening_deduction_ft=Decimal('0'), junctions=None):
    """Dispatch a CalculationRule's formula_kind against a measurement and the
    Trace's settings snapshot. Returns (raw_quantity, piece_length_ft_or_None).
    Pure - no DB writes."""
    if rule.formula_id:
        return max(0, math.ceil(rule.formula.evaluate(measurement))), None

    kind = rule.formula_kind

    if kind == Kind.PER_SPACING:
        junctions = junctions or NO_JUNCTIONS
        junction_extra = (
            junctions['corner_count'] * rule.corner_stud_count
            + junctions['partition_t_count'] * rule.t_intersection_stud_count
            + junctions['through_t_count'] * rule.t_backer_stud_count
        )
        length_ft = max(Decimal('0'), measurement['length_ft'] - opening_deduction_ft)
        count = math.ceil((length_ft * 12) / _spacing_in(settings)) + rule.extra + junction_extra
        # Stud cut length comes from the wall height snapshot when present -
        # minus the plate allowance, since wall_height_in is the overall
        # assembled height (e.g. 97.125" for an 8'-1-1/8" wall), not the stud's
        # own length (92.625" there). Matches plans.framing's elevation preview
        # exactly, so the two never disagree about what a wall's studs are cut to.
        wall_height_in = settings.get('wall_height_in')
        piece_length = None
        if wall_height_in:
            stud_length_ft = (Decimal(str(wall_height_in)) - STANDARD_PLATE_ALLOWANCE_IN) / 12
            if stud_length_ft > 0:
                piece_length = _stock_length_or_none(rule.material, stud_length_ft)
        return count, piece_length

    if kind == Kind.PER_STOCK_LENGTH:
        # Lines measure a run directly; areas contribute their perimeter
        # (e.g. rim board around a floor deck).
        run_ft = measurement.get('length_ft', measurement.get('perimeter_ft'))
        default_length = rule.material.default_length_ft
        return math.ceil(run_ft / default_length) * rule.multiplier, default_length

    if kind == Kind.PER_LENGTH:
        length_ft = measurement['length_ft']
        return rule.multiplier, _stock_length_or_none(rule.material, length_ft)

    if kind == Kind.PER_LENGTH_SPLICED:
        length_ft = measurement['length_ft']
        pieces, piece_length = _spliced_pieces(rule.material, length_ft)
        return rule.multiplier * pieces, piece_length

    if kind == Kind.PER_AREA_SPACING:
        run_ft, member_length_ft = _area_members(measurement, settings)
        count = (math.ceil((run_ft * 12) / _spacing_in(settings)) + 1 + rule.extra) * rule.multiplier
        return count, _stock_length_or_none(rule.material, member_length_ft)

    if kind == Kind.PER_AREA_SPACING_SPLICED:
        run_ft, member_length_ft = _area_members(measurement, settings)
        member_count = (math.ceil((run_ft * 12) / _spacing_in(settings)) + 1 + rule.extra) * rule.multiplier
        pieces, piece_length = _spliced_pieces(rule.material, member_length_ft)
        return member_count * pieces, piece_length

    if kind == Kind.PER_AREA_COVERAGE:
        if not rule.coverage_sqft:
            raise ValueError(f'{rule} needs coverage_sqft for per_area_coverage.')
        return math.ceil(measurement['area_sqft'] / rule.coverage_sqft) * rule.multiplier, None

    if kind == Kind.PER_COUNT:
        return measurement['count'] * rule.multiplier + rule.extra, None

    if kind == Kind.HEADER:
        width_ft = measurement['length_ft'] + HEADER_BEARING_FT
        return rule.multiplier, _stock_length_or_none(rule.material, width_ft)

    if kind == Kind.FIXED_COUNT:
        return rule.multiplier + rule.extra, None

    if kind == Kind.PER_BOX:
        if not rule.units_per_measurement:
            raise ValueError(f'{rule} needs units_per_measurement for per_box.')
        total_units = _primary_measurement_value(measurement) * rule.units_per_measurement
        return rule.material.boxes_needed(total_units) * rule.multiplier, None

    raise ValueError(f'Unknown formula_kind: {kind}')


def calculate_raw_quantity(rule, measurement, settings, opening_deduction_ft=Decimal('0'), junctions=None):
    """Backward-compatible quantity-only wrapper around evaluate_rule().
    Accepts either a measurement dict or a bare length in feet."""
    if not isinstance(measurement, dict):
        measurement = {'length_ft': Decimal(str(measurement))}
    quantity, _ = evaluate_rule(rule, measurement, settings, opening_deduction_ft, junctions)
    return quantity


def apply_waste(raw_quantity, waste_factor):
    """Round up after applying a waste factor, e.g. 0.10 -> 10% extra."""
    return math.ceil(Decimal(raw_quantity) * (Decimal('1') + waste_factor))


def generate_line_items(estimate, assembly, measurement, settings=None, trace=None):
    """Apply every CalculationRule in `assembly` against `measurement` and
    `settings`, (re)creating LineItems on `estimate`. If `trace` is given,
    any LineItems previously generated for that trace are replaced first -
    manual LineItems (trace=None) are never touched, since they can't match
    that filter. `measurement` may be a bare length in feet (line tools) or a
    measurement dict."""
    settings = settings or {}
    if not isinstance(measurement, dict):
        measurement = {'length_ft': Decimal(str(measurement))}
    if trace is not None:
        LineItem.objects.filter(estimate=estimate, trace=trace).delete()

    opening_deduction_ft = _attached_opening_width_ft(trace)
    junctions = detect_wall_junctions(trace) if trace is not None else None

    created = []
    for rule in assembly.rules.select_related('material', 'formula', 'formula__base_formula').order_by('order'):
        raw_quantity, piece_length_ft = evaluate_rule(rule, measurement, settings, opening_deduction_ft, junctions)
        quantity = apply_waste(raw_quantity, rule.waste_factor)
        created.append(LineItem.objects.create(
            estimate=estimate, trace=trace, calculation_rule=rule, material=rule.material,
            role=rule.role, category=assembly.category, length_ft=piece_length_ft, quantity=quantity,
            waste_factor=rule.waste_factor, source=LineItem.Source.TOOL,
        ))
    return created
