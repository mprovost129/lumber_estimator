import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView

from catalog.models import MaterialProduct
from projects.models import JobSettings, Project

from .forms import PlanUploadForm
from .models import PlanPage, ToolPreset, Trace
from .services import rasterize_plan


def _resolve_material(account, material_id):
    """Look up a material by id, scoped to what's visible to the account.
    Returns (material, None) or (None, error_message) if material_id was given but invalid."""
    if not material_id:
        return None, None
    material = MaterialProduct.objects.visible_to(account).filter(pk=material_id).first()
    if material is None:
        return None, 'Invalid material.'
    return material, None


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
        return redirect('projects:detail', pk=page.plan.project_id)


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

        materials = MaterialProduct.objects.visible_to(account).filter(input_type=MaterialProduct.InputType.FT)
        presets = ToolPreset.objects.filter(account=account, tool_type=Trace.ToolType.LINE)
        traces = page.traces.select_related('material')

        context.update({
            'project': page.plan.project,
            'materials': materials,
            'presets': presets,
            'default_stud_spacing_in': default_stud_spacing_in,
            'traces': list(traces.values('id', 'tool_type', 'geometry', 'settings', 'material_id')),
            'presets_data': list(presets.values('id', 'name', 'material_id', 'settings')),
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
        material_id = payload.get('material_id')

        if tool_type not in Trace.ToolType.values:
            return JsonResponse({'error': 'Invalid tool_type.'}, status=400)
        if not geometry:
            return JsonResponse({'error': 'geometry is required.'}, status=400)

        material, error = _resolve_material(account, material_id)
        if error:
            return JsonResponse({'error': error}, status=400)

        trace = Trace.objects.create(
            plan_page=page, tool_type=tool_type, geometry=geometry,
            material=material, settings=settings_data,
        )
        return JsonResponse({
            'id': trace.id,
            'tool_type': trace.tool_type,
            'geometry': trace.geometry,
            'settings': trace.settings,
            'material_id': trace.material_id,
            'material_name': trace.material.name if trace.material else None,
        }, status=201)


class TraceUpdateView(LoginRequiredMixin, View):
    """Edit an existing Trace's material/settings (not its geometry or tool_type) —
    the sidebar's "selected wall" inspector panel."""

    def post(self, request, pk):
        account = request.user.account
        trace = get_object_or_404(Trace.objects.for_account(account), pk=pk)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)

        material, error = _resolve_material(account, payload.get('material_id'))
        if error:
            return JsonResponse({'error': error}, status=400)

        trace.material = material
        trace.settings = payload.get('settings') or {}
        trace.save(update_fields=['material', 'settings'])

        return JsonResponse({
            'id': trace.id,
            'tool_type': trace.tool_type,
            'geometry': trace.geometry,
            'settings': trace.settings,
            'material_id': trace.material_id,
            'material_name': trace.material.name if trace.material else None,
        })


class TraceDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        trace = get_object_or_404(Trace.objects.for_account(request.user.account), pk=pk)
        trace.delete()
        return JsonResponse({'deleted': True})


class ToolPresetListCreateView(LoginRequiredMixin, View):
    def get(self, request):
        tool_type = request.GET.get('tool_type', Trace.ToolType.LINE)
        presets = ToolPreset.objects.filter(account=request.user.account, tool_type=tool_type)
        return JsonResponse({'presets': list(presets.values('id', 'name', 'material_id', 'settings'))})

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

        if not name:
            return JsonResponse({'error': 'name is required.'}, status=400)
        if tool_type not in Trace.ToolType.values:
            return JsonResponse({'error': 'Invalid tool_type.'}, status=400)

        material, error = _resolve_material(account, material_id)
        if error:
            return JsonResponse({'error': error}, status=400)

        preset, created = ToolPreset.objects.update_or_create(
            account=account, tool_type=tool_type, name=name,
            defaults={'material': material, 'settings': settings_data},
        )
        return JsonResponse({
            'id': preset.id,
            'name': preset.name,
            'material_id': preset.material_id,
            'settings': preset.settings,
        }, status=201 if created else 200)
