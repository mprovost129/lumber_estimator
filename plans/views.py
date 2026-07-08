import json
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView

from catalog.models import MaterialProduct
from estimating.calculations import generate_line_items
from estimating.models import Assembly, LineItem
from projects.models import JobSettings, Project

from .forms import PlanUploadForm
from .framing import build_wall_elevation, validate_wall_member_overrides
from .geometry import measure_geometry, pixel_length
from .models import PlanPage, ToolPreset, Trace
from .services import RENDER_ZOOM, rasterize_plan
from .wall_junctions import could_share_a_junction


def _resolve_material(account, material_id):
    """Look up a material by id, scoped to what's visible to the account.
    Returns (material, None) or (None, error_message) if material_id was given but invalid."""
    if not material_id:
        return None, None
    material = MaterialProduct.objects.visible_to(account).filter(pk=material_id).first()
    if material is None:
        return None, 'Invalid material.'
    return material, None


def _resolve_assembly(account, assembly_id, tool_type, settings=None):
    """Look up an assembly by id, scoped to what's visible to the account and
    matching the trace's tool_type. Returns (assembly, None) or (None, error_message)."""
    if not assembly_id:
        return None, None
    compatible_types = [tool_type]
    if tool_type == Trace.ToolType.POLYLINE:
        compatible_types.append(
            Trace.ToolType.AREA if (settings or {}).get('closed') else Trace.ToolType.LINE,
        )
    assembly = Assembly.objects.visible_to(account).filter(
        pk=assembly_id, tool_type__in=compatible_types,
    ).first()
    if assembly is None:
        return None, 'Invalid assembly.'
    return assembly, None


def _resolve_parent_wall(account, parent_wall_id, page, tool_type):
    """Look up a wall trace to attach an opening to. Returns (wall_or_None,
    error_or_None). Only opening traces may set a parent_wall; the referenced
    trace must be a line/polyline trace on the same PlanPage (and, via the
    tenancy-scoped queryset, the same account)."""
    if not parent_wall_id:
        return None, None
    if tool_type != Trace.ToolType.OPENING:
        return None, 'Only opening traces can be attached to a wall.'
    wall = Trace.objects.for_account(account).filter(
        pk=parent_wall_id, plan_page=page, tool_type__in=[Trace.ToolType.LINE, Trace.ToolType.POLYLINE],
    ).first()
    if wall is None:
        return None, 'Invalid parent wall.'
    return wall, None


def _peek_parent_wall(account, parent_wall_id, page):
    """Best-effort lookup of a candidate parent wall, for dynamic opening
    assembly resolution only - returns None on any failure (bad id, wrong
    page, wrong account) rather than an error. The real _resolve_parent_wall()
    call still runs later at its existing point in each view and is what
    actually validates and rejects a bad attachment, so error precedence for
    an invalid request is unchanged by this peek."""
    if not parent_wall_id:
        return None
    return Trace.objects.for_account(account).filter(
        pk=parent_wall_id, plan_page=page, tool_type__in=[Trace.ToolType.LINE, Trace.ToolType.POLYLINE],
    ).first()


def _resolve_opening_assembly(account, settings_data, parent_wall):
    """For an opening trace with a candidate parent wall, auto-match the
    Assembly by that wall's own assembly.wall_subtype + this opening's
    window/door kind (settings_data['opening_type']). Returns an Assembly or
    None - None means "couldn't auto-resolve," and the caller falls back to
    whatever assembly_id the client explicitly sent. A manually-sent
    assembly_id is intentionally ignored whenever a wall match succeeds -
    full automation is the deliberate choice here, not an oversight, so the
    opening's materials can never silently drift out of sync with whichever
    wall it's actually attached to."""
    if parent_wall is None or parent_wall.assembly_id is None or not parent_wall.assembly.wall_subtype:
        return None
    opening_kind = (settings_data or {}).get('opening_type') or Assembly.OpeningKind.WINDOW
    return Assembly.objects.visible_to(account).filter(
        tool_type=Trace.ToolType.OPENING, opening_kind=opening_kind, wall_subtype=parent_wall.assembly.wall_subtype,
    ).first()


MIN_POINTS = {'line': 2, 'polyline': 2, 'opening': 2, 'area': 3, 'count': 1}
HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')


def _validate_geometry(tool_type, geometry, settings=None):
    """Basic shape check per tool. Returns an error message or None."""
    if not isinstance(geometry, list) or not all(
        isinstance(p, dict) and 'x' in p and 'y' in p for p in geometry
    ):
        return 'geometry must be a list of {x, y} points.'
    if len(geometry) < MIN_POINTS.get(tool_type, 2):
        return f'{tool_type} traces need at least {MIN_POINTS[tool_type]} points.'
    if tool_type == Trace.ToolType.POLYLINE and (settings or {}).get('closed') and len(geometry) < 3:
        return 'Closed polyline traces need at least 3 points.'
    return None


def _validate_color(color):
    if color and not HEX_COLOR_RE.fullmatch(color):
        return 'color must be a six-digit hex value, e.g. #0d6efd.'
    return None


def _measurement_display(tool_type, measurement):
    """Short human-readable summary shown next to a trace in the viewer."""
    if tool_type == 'count':
        return f"{measurement['count']} pts"
    if tool_type == 'area' or (tool_type == 'polyline' and 'area_sqft' in measurement):
        return f"{measurement['area_sqft']:.0f} sq ft"
    return f"{measurement['length_ft']:.1f} ft"


def _regenerate_wall_line_items(wall_trace):
    """Re-run the calc engine for a wall trace whose set of attached openings
    just changed (one was attached, detached, or reattached elsewhere), so its
    stud count reflects the current opening deduction. No-op if the wall has
    no assembly assigned or its page isn't calibrated - there are no LineItems
    to keep in sync in either case."""
    if wall_trace is None or wall_trace.assembly_id is None:
        return
    scale = wall_trace.plan_page.scale_pixels_per_foot
    if scale is None:
        return
    measurement = measure_geometry(wall_trace.tool_type, wall_trace.geometry, scale, wall_trace.settings)
    estimate = wall_trace.plan_page.plan.project.get_or_create_estimate()
    generate_line_items(estimate, wall_trace.assembly, measurement, wall_trace.settings, trace=wall_trace)


def _regenerate_sibling_walls(trace):
    """A newly created (or just-deleted) wall can add or remove a corner/T
    junction with existing walls on the same page - recompute the LineItems
    of any sibling wall that could plausibly be affected, so the extra studs
    show up/disappear without the user having to manually re-save each
    neighboring wall. Cheaply pre-filters to siblings with a point near one
    of trace's own two endpoints before doing the full recompute, so adding
    one wall to a page with many others doesn't recompute all of them."""
    siblings = Trace.objects.filter(
        plan_page_id=trace.plan_page_id, tool_type__in=[Trace.ToolType.LINE, Trace.ToolType.POLYLINE],
    ).exclude(pk=trace.pk)
    for sibling in siblings:
        if could_share_a_junction(trace, sibling):
            _regenerate_wall_line_items(sibling)


def _trace_payload(trace, measurement=None):
    payload = {
        'id': trace.id,
        'tool_type': trace.tool_type,
        'geometry': trace.geometry,
        'settings': trace.settings,
        'color': trace.color,
        'material_id': trace.material_id,
        'material_name': trace.material.name if trace.material else None,
        'assembly_id': trace.assembly_id,
        'assembly_name': trace.assembly.name if trace.assembly else None,
        'parent_wall_id': trace.parent_wall_id,
    }
    if measurement is not None:
        payload['measurement_display'] = _measurement_display(trace.tool_type, measurement)
    return payload


def _update_trace_from_payload(account, trace, payload):
    settings_data = payload.get('settings') or {}
    try:
        validate_wall_member_overrides(settings_data.get('wall_member_overrides'))
    except ValueError as exc:
        return None, str(exc)

    material, error = _resolve_material(account, payload.get('material_id'))
    if error:
        return None, error

    assembly = None
    if trace.tool_type == Trace.ToolType.OPENING:
        candidate_wall = _peek_parent_wall(account, payload.get('parent_wall_id'), trace.plan_page)
        assembly = _resolve_opening_assembly(account, settings_data, candidate_wall)
    if assembly is None:
        assembly, error = _resolve_assembly(
            account, payload.get('assembly_id'), trace.tool_type, settings_data,
        )
        if error:
            return None, error

    needs_scale = trace.tool_type != Trace.ToolType.COUNT
    if assembly is not None and needs_scale and trace.plan_page.scale_pixels_per_foot is None:
        return None, 'Calibrate this page before assigning an assembly.'

    parent_wall, error = _resolve_parent_wall(
        account, payload.get('parent_wall_id'), trace.plan_page, trace.tool_type,
    )
    if error:
        return None, error

    color = payload.get('color') or ''
    error = _validate_color(color)
    if error:
        return None, error

    old_parent_wall = trace.parent_wall
    old_parent_wall_id = trace.parent_wall_id
    measurement = None
    try:
        with transaction.atomic():
            trace.material = material
            trace.assembly = assembly
            trace.parent_wall = parent_wall
            trace.settings = settings_data
            trace.color = color
            trace.save(update_fields=['material', 'assembly', 'parent_wall', 'settings', 'color'])
            scale = trace.plan_page.scale_pixels_per_foot
            if scale is not None or not needs_scale:
                measurement = measure_geometry(
                    trace.tool_type, trace.geometry, scale or 1, settings_data,
                )
            if assembly is not None:
                estimate = trace.plan_page.plan.project.get_or_create_estimate()
                generate_line_items(estimate, assembly, measurement, settings_data, trace=trace)
            else:
                LineItem.objects.filter(trace=trace).delete()
            if old_parent_wall_id != trace.parent_wall_id:
                if old_parent_wall is not None:
                    _regenerate_wall_line_items(old_parent_wall)
                if trace.parent_wall is not None:
                    _regenerate_wall_line_items(trace.parent_wall)
    except (ValueError, KeyError) as exc:
        return None, str(exc)

    return measurement, None


class PlanUploadView(LoginRequiredMixin, View):
    def post(self, request, project_id):
        project = get_object_or_404(Project.objects.for_account(request.user.account), pk=project_id)
        form = PlanUploadForm(request.POST, request.FILES)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.project = project
            plan.save()
            pages = rasterize_plan(plan)
            messages.success(request, f'Uploaded {plan.name} ({len(pages)} pages).')
            if pages and request.POST.get('open_after_upload', '1') != '0':
                messages.info(request, 'Calibrate this page to start tracing.')
                return redirect('plans:viewer', pk=pages[0].pk)
        else:
            errors = '; '.join(
                f'{field}: {", ".join(field_errors)}' for field, field_errors in form.errors.items()
            )
            messages.error(request, f'Could not upload plan: {errors}')
        return redirect('projects:detail', pk=project.pk)


class PlanPageLabelUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        page = get_object_or_404(PlanPage.objects.for_account(request.user.account), pk=pk)
        page.label = request.POST.get('label', '').strip()
        page.save(update_fields=['label'])
        # The viewer renames inline over fetch; the project detail page still
        # posts a plain form. Same endpoint, response keyed off the header.
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'label': page.label, 'display_label': page.display_label})
        return redirect('projects:detail', pk=page.plan.project_id)


class PlanPageDeleteView(LoginRequiredMixin, View):
    """Deletes a single rasterized page - not every page in an uploaded PDF is
    always wanted. Cascades to that page's Traces and their LineItems (the
    existing FK cascade, same as deleting a Trace directly); the page's own
    image/thumbnail files are removed from storage too, since nothing else
    references them once the row is gone."""

    def post(self, request, pk):
        page = get_object_or_404(PlanPage.objects.for_account(request.user.account), pk=pk)
        project_id = page.plan.project_id
        label = page.display_label
        image, thumbnail = page.image, page.thumbnail
        page.delete()
        image.delete(save=False)
        thumbnail.delete(save=False)
        messages.success(request, f'{label} deleted.')
        return redirect('projects:detail', pk=project_id)


POINTS_PER_INCH = 72  # PDF/PostScript unit - PyMuPDF's zoom is relative to this.
PIXELS_PER_INCH = RENDER_ZOOM * POINTS_PER_INCH  # matches plans.services' rasterization DPI


class PlanPageCalibrateView(LoginRequiredMixin, View):
    """Sets a PlanPage's pixels-per-foot scale, either (a) from a drawn
    reference line plus the real-world length the user says that line
    represents, or (b) directly from a stated architectural drawing scale
    (e.g. "1/4 in = 1 ft") - no line needed for (b), since plans.services
    rasterizes PDF pages at a fixed, known DPI (RENDER_ZOOM), so a stated
    print scale alone fully determines pixels-per-foot. (b) is only accurate
    for pages actually rendered at that DPI (PDF uploads) - a plain image
    upload's real DPI is unknown/arbitrary, so a preset scale will silently
    be wrong there; (a) remains the reliable option for those pages."""

    def post(self, request, pk):
        page = get_object_or_404(PlanPage.objects.for_account(request.user.account), pk=pk)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)

        if payload.get('scale_inches_per_foot') is not None:
            return self._calibrate_from_preset(page, payload)
        return self._calibrate_from_geometry(page, payload)

    def _calibrate_from_preset(self, page, payload):
        try:
            scale_inches_per_foot = Decimal(str(payload['scale_inches_per_foot']))
        except InvalidOperation:
            return JsonResponse({'error': 'scale_inches_per_foot must be a number.'}, status=400)
        if scale_inches_per_foot <= 0:
            return JsonResponse({'error': 'scale_inches_per_foot must be positive.'}, status=400)

        page.scale_pixels_per_foot = Decimal(str(PIXELS_PER_INCH)) * scale_inches_per_foot
        page.save(update_fields=['scale_pixels_per_foot'])
        return JsonResponse({'scale_pixels_per_foot': str(page.scale_pixels_per_foot)})

    def _calibrate_from_geometry(self, page, payload):
        geometry = payload.get('geometry')
        known_length_ft = payload.get('known_length_ft')
        if not geometry or known_length_ft is None:
            return JsonResponse({'error': 'geometry and known_length_ft are required.'}, status=400)

        try:
            known_length_ft = Decimal(str(known_length_ft))
        except InvalidOperation:
            return JsonResponse({'error': 'known_length_ft must be a number.'}, status=400)
        if known_length_ft <= 0:
            return JsonResponse({'error': 'known_length_ft must be positive.'}, status=400)

        pixels = pixel_length(geometry)
        if pixels <= 0:
            return JsonResponse({'error': 'geometry must describe a non-zero length.'}, status=400)

        page.scale_pixels_per_foot = Decimal(str(pixels)) / known_length_ft
        page.save(update_fields=['scale_pixels_per_foot'])
        return JsonResponse({'scale_pixels_per_foot': str(page.scale_pixels_per_foot)})


class PlanViewerView(LoginRequiredMixin, DetailView):
    model = PlanPage
    template_name = 'plans/viewer.html'
    context_object_name = 'page'

    def get_queryset(self):
        return PlanPage.objects.for_account(self.request.user.account)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = self.request.user.account
        page = self.object

        job_settings = getattr(page.plan.project, 'job_settings', None)
        default_stud_spacing_in = job_settings.stud_spacing_in if job_settings else JobSettings.StudSpacing.SIXTEEN_OC
        default_wall_height_in = (
            job_settings.first_floor_wall_height_in if job_settings
            else JobSettings._meta.get_field('first_floor_wall_height_in').default
        )

        materials = MaterialProduct.objects.visible_to(account)
        assemblies = Assembly.objects.visible_to(account)
        presets = ToolPreset.objects.filter(account=account)
        traces = page.traces.select_related('material', 'assembly')

        walls = page.traces.filter(tool_type__in=[Trace.ToolType.LINE, Trace.ToolType.POLYLINE])
        estimate = page.plan.project.get_or_create_estimate()

        # Every page in the project (across all its plans), oldest plan first,
        # for the in-viewer page switcher strip. Hopping floors/pages should
        # never require going back through the project detail page.
        project_pages = (
            PlanPage.objects.filter(plan__project=page.plan.project)
            .select_related('plan')
            .order_by('plan__uploaded_at', 'page_number')
        )

        context.update({
            'project': page.plan.project,
            'estimate': estimate,
            'materials': materials,
            'project_pages': project_pages,
            'default_stud_spacing_in': default_stud_spacing_in,
            'default_wall_height_in': default_wall_height_in,
            'is_calibrated': page.scale_pixels_per_foot is not None,
            'traces': list(traces.values(
                'id', 'tool_type', 'geometry', 'settings', 'color', 'material_id', 'assembly_id', 'parent_wall_id',
            )),
            'materials_data': list(materials.values('id', 'name', 'input_type')),
            'assemblies_data': list(assemblies.values(
                'id', 'name', 'tool_type', 'category', 'wall_subtype', 'opening_kind', 'beam_type', 'is_default',
            )),
            'presets_data': list(presets.values(
                'id', 'name', 'tool_type', 'material_id', 'settings', 'color',
            )),
            'walls_data': list(walls.values('id', 'tool_type')),
        })
        return context


class TraceCreateView(LoginRequiredMixin, View):
    def post(self, request, page_id):
        account = request.user.account
        page = get_object_or_404(PlanPage.objects.for_account(account), pk=page_id)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)

        tool_type = payload.get('tool_type')
        geometry = payload.get('geometry')
        settings_data = payload.get('settings') or {}
        color = payload.get('color') or ''
        material_id = payload.get('material_id')
        assembly_id = payload.get('assembly_id')

        if tool_type not in Trace.ToolType.values:
            return JsonResponse({'error': 'Invalid tool_type.'}, status=400)
        if not geometry:
            return JsonResponse({'error': 'geometry is required.'}, status=400)
        error = _validate_geometry(tool_type, geometry, settings_data)
        if error:
            return JsonResponse({'error': error}, status=400)
        error = _validate_color(color)
        if error:
            return JsonResponse({'error': error}, status=400)
        try:
            validate_wall_member_overrides(settings_data.get('wall_member_overrides'))
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        material, error = _resolve_material(account, material_id)
        if error:
            return JsonResponse({'error': error}, status=400)

        assembly = None
        if tool_type == Trace.ToolType.OPENING:
            candidate_wall = _peek_parent_wall(account, payload.get('parent_wall_id'), page)
            assembly = _resolve_opening_assembly(account, settings_data, candidate_wall)
        if assembly is None:
            assembly, error = _resolve_assembly(account, assembly_id, tool_type, settings_data)
            if error:
                return JsonResponse({'error': error}, status=400)
        # Count tools need no calibration; everything else measures real distances.
        needs_scale = tool_type != Trace.ToolType.COUNT
        if assembly is not None and needs_scale and page.scale_pixels_per_foot is None:
            return JsonResponse({'error': 'Calibrate this page before assigning an assembly.'}, status=400)

        parent_wall, error = _resolve_parent_wall(account, payload.get('parent_wall_id'), page, tool_type)
        if error:
            return JsonResponse({'error': error}, status=400)

        measurement = None
        try:
            with transaction.atomic():
                trace = Trace.objects.create(
                    plan_page=page, tool_type=tool_type, geometry=geometry,
                    material=material, assembly=assembly, parent_wall=parent_wall,
                    settings=settings_data, color=color,
                )
                if page.scale_pixels_per_foot is not None or not needs_scale:
                    measurement = measure_geometry(
                        tool_type, geometry, page.scale_pixels_per_foot or 1, settings_data,
                    )
                if assembly is not None:
                    estimate = page.plan.project.get_or_create_estimate()
                    generate_line_items(estimate, assembly, measurement, settings_data, trace=trace)
                if parent_wall is not None:
                    _regenerate_wall_line_items(parent_wall)
                if tool_type in (Trace.ToolType.LINE, Trace.ToolType.POLYLINE):
                    _regenerate_sibling_walls(trace)
        except (ValueError, KeyError) as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        return JsonResponse(_trace_payload(trace, measurement), status=201)


class WallElevationView(LoginRequiredMixin, View):
    """Read-only generated framing preview for a selected wall trace.

    This is the first slice of the intelligent wall-object workflow: the trace
    remains the plan control line, while the wall elevation is generated from
    its assembly/settings and nearby opening traces.
    """

    def get(self, request, pk):
        trace = get_object_or_404(Trace.objects.for_account(request.user.account), pk=pk)
        try:
            return JsonResponse(build_wall_elevation(trace))
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)


class TraceUpdateView(LoginRequiredMixin, View):
    """Edit an existing Trace's material/assembly/settings (not its geometry
    or tool_type) - the sidebar's "selected wall" inspector panel."""

    def post(self, request, pk):
        account = request.user.account
        trace = get_object_or_404(Trace.objects.for_account(account), pk=pk)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)
        measurement, error = _update_trace_from_payload(account, trace, payload)
        if error:
            return JsonResponse({'error': error}, status=400)

        return JsonResponse(_trace_payload(trace, measurement))


class TraceBatchUpdateView(LoginRequiredMixin, View):
    def post(self, request):
        account = request.user.account
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)

        trace_ids = payload.get('trace_ids')
        if not isinstance(trace_ids, list) or not trace_ids:
            return JsonResponse({'error': 'trace_ids must be a non-empty list.'}, status=400)

        traces = list(Trace.objects.for_account(account).filter(pk__in=trace_ids).select_related('plan_page__plan__project'))
        if len(traces) != len(set(trace_ids)):
            return JsonResponse({'error': 'One or more traces were not found.'}, status=404)

        apply_material = bool(payload.get('apply_material'))
        apply_assembly = bool(payload.get('apply_assembly'))
        apply_color = bool(payload.get('apply_color'))
        apply_settings = bool(payload.get('apply_settings'))

        if not any([apply_material, apply_assembly, apply_color, apply_settings]):
            return JsonResponse({'error': 'No batch changes were requested.'}, status=400)

        tool_types = {trace.tool_type for trace in traces}
        if len(tool_types) > 1 and (apply_assembly or apply_settings):
            return JsonResponse({'error': 'Assembly or settings can only be batch-applied to traces of the same type.'}, status=400)

        first_tool_type = traces[0].tool_type
        results = []
        with transaction.atomic():
            for trace in traces:
                trace_payload = {
                    'material_id': payload.get('material_id') if apply_material else trace.material_id,
                    'assembly_id': payload.get('assembly_id') if apply_assembly else trace.assembly_id,
                    'parent_wall_id': payload.get('parent_wall_id') if first_tool_type == Trace.ToolType.OPENING and apply_settings else trace.parent_wall_id,
                    'color': payload.get('color') if apply_color else trace.color,
                    'settings': payload.get('settings') if apply_settings else trace.settings,
                }
                measurement, error = _update_trace_from_payload(account, trace, trace_payload)
                if error:
                    transaction.set_rollback(True)
                    return JsonResponse({'error': error}, status=400)
                results.append(_trace_payload(trace, measurement))

        return JsonResponse({'traces': results})


class TraceDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        trace = get_object_or_404(Trace.objects.for_account(request.user.account), pk=pk)
        parent_wall = trace.parent_wall if trace.tool_type == Trace.ToolType.OPENING else None
        sibling_walls = []
        if trace.tool_type in (Trace.ToolType.LINE, Trace.ToolType.POLYLINE):
            sibling_walls = list(
                Trace.objects.filter(
                    plan_page_id=trace.plan_page_id, tool_type__in=[Trace.ToolType.LINE, Trace.ToolType.POLYLINE],
                ).exclude(pk=trace.pk)
            )
        trace.delete()
        # Deletion already succeeded above; don't fail the request over a
        # stale-recalculation edge case in some other trace - the affected
        # wall's LineItems just stay as they were until its next successful edit.
        if parent_wall is not None:
            try:
                _regenerate_wall_line_items(parent_wall)
            except (ValueError, KeyError):
                pass
        for wall in sibling_walls:
            if could_share_a_junction(trace, wall):
                try:
                    _regenerate_wall_line_items(wall)
                except (ValueError, KeyError):
                    pass
        return JsonResponse({'deleted': True})


class TraceBatchDeleteView(LoginRequiredMixin, View):
    def post(self, request):
        account = request.user.account
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)

        trace_ids = payload.get('trace_ids')
        if not isinstance(trace_ids, list) or not trace_ids:
            return JsonResponse({'error': 'trace_ids must be a non-empty list.'}, status=400)

        traces = list(Trace.objects.for_account(account).filter(pk__in=trace_ids).select_related('parent_wall'))
        if len(traces) != len(set(trace_ids)):
            return JsonResponse({'error': 'One or more traces were not found.'}, status=404)

        trace_ids_set = {trace.pk for trace in traces}
        parent_walls = [trace.parent_wall for trace in traces if trace.tool_type == Trace.ToolType.OPENING and trace.parent_wall_id]
        deleted_walls = [trace for trace in traces if trace.tool_type in (Trace.ToolType.LINE, Trace.ToolType.POLYLINE)]
        sibling_walls = list(
            Trace.objects.filter(
                plan_page_id__in={trace.plan_page_id for trace in deleted_walls},
                tool_type__in=[Trace.ToolType.LINE, Trace.ToolType.POLYLINE],
            ).exclude(pk__in=trace_ids_set)
        ) if deleted_walls else []

        with transaction.atomic():
            Trace.objects.filter(pk__in=trace_ids_set).delete()

        for wall in parent_walls:
            try:
                _regenerate_wall_line_items(wall)
            except (ValueError, KeyError):
                pass
        for wall in sibling_walls:
            if any(could_share_a_junction(deleted_trace, wall) for deleted_trace in deleted_walls):
                try:
                    _regenerate_wall_line_items(wall)
                except (ValueError, KeyError):
                    pass
        return JsonResponse({'deleted': True, 'count': len(traces)})


class ToolPresetListCreateView(LoginRequiredMixin, View):
    def get(self, request):
        tool_type = request.GET.get('tool_type', Trace.ToolType.LINE)
        presets = ToolPreset.objects.filter(account=request.user.account, tool_type=tool_type)
        return JsonResponse({'presets': list(
            presets.values('id', 'name', 'material_id', 'settings', 'color'),
        )})

    def post(self, request):
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)

        account = request.user.account
        name = (payload.get('name') or '').strip()
        tool_type = payload.get('tool_type')
        material_id = payload.get('material_id')
        settings_data = payload.get('settings') or {}
        color = payload.get('color') or ''

        if not name:
            return JsonResponse({'error': 'name is required.'}, status=400)
        if tool_type not in Trace.ToolType.values:
            return JsonResponse({'error': 'Invalid tool_type.'}, status=400)

        material, error = _resolve_material(account, material_id)
        if error:
            return JsonResponse({'error': error}, status=400)
        error = _validate_color(color)
        if error:
            return JsonResponse({'error': error}, status=400)

        preset, created = ToolPreset.objects.update_or_create(
            account=account, tool_type=tool_type, name=name,
            defaults={'material': material, 'settings': settings_data, 'color': color},
        )
        return JsonResponse({
            'id': preset.id,
            'name': preset.name,
            'material_id': preset.material_id,
            'settings': preset.settings,
            'color': preset.color,
        }, status=201 if created else 200)
