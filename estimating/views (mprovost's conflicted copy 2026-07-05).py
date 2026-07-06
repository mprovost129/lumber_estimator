import csv
import itertools
import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Min, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, TemplateView

from accounts.models import Account
from projects.models import Estimate

from .forms import AssemblyForm, CalculationRuleFormSet, FormulaForm, ManualLineItemForm
from .models import Assembly, Formula, LineItem

CATEGORY_DEFAULT_ORDER = list(Assembly.Category.values)
CATEGORY_LABELS = dict(Assembly.Category.choices)
VALID_CATEGORIES = set(Assembly.Category.values)


def _effective_category():
    """A global assembly's classification can be edited after LineItems
    already exist with the old category baked in (LineItem.category is
    denormalized, since calculation_rule is SET_NULL and manual lines have no
    assembly at all) - Coalesce prefers the live assembly category so an
    after-the-fact fix shows up without regenerating every LineItem, falling
    back to the stored column for manual/orphaned rows. Both the Detail view
    and the CSV rollup use this so they never disagree."""
    return Coalesce('calculation_rule__assembly__category', 'category')


def _category_order_for(account):
    """The account's preferred group order, falling back to (and filling any
    gaps from) the doc's default order - a category with no saved preference
    yet (new account, or a category introduced since the account last
    reordered) never silently disappears from the page."""
    saved = [c for c in (account.category_order or []) if c in VALID_CATEGORIES]
    saved += [c for c in CATEGORY_DEFAULT_ORDER if c not in saved]
    return saved


def _item_rank(account, category, role):
    """Position of `role` within its category's saved item order, matched
    case/whitespace-insensitively - the seed data itself has near-duplicate
    role strings across assemblies (e.g. "Bottom Plate" vs "Bottom Plate
    (PT)") that won't share a saved rank without this. Unranked roles sort
    last, in whatever order they were already in."""
    order = (account.item_order or {}).get(category, [])
    normalized = [r.strip().lower() for r in order]
    key = (role or '').strip().lower()
    return normalized.index(key) if key in normalized else len(normalized)


def _grouped_order_list(estimate):
    """The supplier-ready view: line items grouped by product + piece length
    *and* construction system (so the same SKU used under two different
    systems, e.g. 2x6 SPF #2 in both walls and blocking, never merges into
    one row) with summed quantities, ordered to match the Detail page."""
    account = estimate.project.account
    category_rank = {c: i for i, c in enumerate(_category_order_for(account))}
    rows = list(
        estimate.line_items
        .annotate(effective_category=_effective_category())
        .order_by()
        .values('effective_category', 'material__name', 'material__nominal_dimension',
                'material__species', 'material__grade', 'length_ft')
        .annotate(total_quantity=Sum('quantity'), min_role=Min('role'))
    )
    # min_role is a deterministic tiebreak for the rare case where a merged
    # row spans more than one role within the same category - not a source
    # of truth for item order at that granularity.
    rows.sort(key=lambda r: (
        category_rank.get(r['effective_category'], len(category_rank)),
        _item_rank(account, r['effective_category'], r['min_role']),
        r['material__name'],
    ))
    for row in rows:
        row['category_label'] = CATEGORY_LABELS.get(row['effective_category'], row['effective_category'])
    return rows


class EstimateDetailView(LoginRequiredMixin, DetailView):
    model = Estimate
    template_name = 'estimating/estimate_detail.html'
    context_object_name = 'estimate'

    def get_queryset(self):
        return Estimate.objects.for_account(self.request.user.account)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = self.request.user.account
        line_items = list(
            self.object.line_items.select_related('material', 'trace')
            .annotate(effective_category=_effective_category())
            .order_by()
        )
        category_rank = {c: i for i, c in enumerate(_category_order_for(account))}
        line_items.sort(key=lambda li: (
            category_rank.get(li.effective_category, len(category_rank)),
            _item_rank(account, li.effective_category, li.role),
        ))
        grouped_line_items = [
            {'key': category, 'label': CATEGORY_LABELS.get(category, category), 'items': list(items)}
            for category, items in itertools.groupby(line_items, key=lambda li: li.effective_category)
        ]
        context['grouped_line_items'] = grouped_line_items
        context['order_list'] = _grouped_order_list(self.object)
        context['manual_form'] = ManualLineItemForm(account=account)
        return context


class EstimateMaterialSummaryView(LoginRequiredMixin, DetailView):
    """Renders a compact, view-only material list partial - reuses the exact
    same _grouped_order_list() rollup as the full Estimate Detail page and
    CSV export, so the numbers can never disagree. Polled by the plan viewer
    after every trace create/update/delete to show a live-updating list next
    to the canvas without a full page reload; no drag-and-drop reordering
    here, that's what "Full view" (a link to the real Estimate Detail page)
    is for."""

    model = Estimate
    template_name = 'estimating/_material_summary.html'
    context_object_name = 'estimate'

    def get_queryset(self):
        return Estimate.objects.for_account(self.request.user.account)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order_list'] = _grouped_order_list(self.object)
        return context


class EstimateCsvExportView(LoginRequiredMixin, View):
    """Download the grouped order list as CSV - the core deliverable."""

    def get(self, request, pk):
        estimate = get_object_or_404(Estimate.objects.for_account(request.user.account), pk=pk)
        response = HttpResponse(content_type='text/csv')
        filename = f'{estimate.project.name} - {estimate.name} - materials.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['System', 'Material', 'Dimension', 'Species/Grade', 'Length (ft)', 'Quantity'])
        for row in _grouped_order_list(estimate):
            species_grade = ' '.join(part for part in (row['material__species'], row['material__grade']) if part)
            writer.writerow([
                row['category_label'],
                row['material__name'],
                row['material__nominal_dimension'],
                species_grade,
                row['length_ft'] or '',
                row['total_quantity'],
            ])
        return response


class CategoryOrderUpdateView(LoginRequiredMixin, View):
    """Saves the requesting account's preferred material-list group order.
    Account-wide by design - applies to every estimate the account has, past
    and future, the next time it's viewed."""

    def post(self, request):
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)
        order = payload.get('order')
        if not isinstance(order, list) or not all(isinstance(c, str) for c in order):
            return JsonResponse({'error': 'order must be a list of category keys.'}, status=400)
        unknown = [c for c in order if c not in VALID_CATEGORIES]
        if unknown:
            return JsonResponse({'error': f'Unknown category key(s): {", ".join(unknown)}.'}, status=400)
        with transaction.atomic():
            account = Account.objects.select_for_update().get(pk=request.user.account_id)
            account.category_order = order
            account.save(update_fields=['category_order'])
        return JsonResponse({'category_order': order})


class ItemOrderUpdateView(LoginRequiredMixin, View):
    """Saves the requesting account's preferred item order within one
    material-list group, keyed by role text (not by LineItem/CalculationRule
    id) so the preference generalizes to future estimates, per the
    account-wide requirement."""

    def post(self, request):
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)
        category = payload.get('category')
        order = payload.get('order')
        if category not in VALID_CATEGORIES:
            return JsonResponse({'error': 'Invalid category.'}, status=400)
        if not isinstance(order, list) or not all(isinstance(r, str) for r in order):
            return JsonResponse({'error': 'order must be a list of role strings.'}, status=400)
        with transaction.atomic():
            account = Account.objects.select_for_update().get(pk=request.user.account_id)
            item_order = dict(account.item_order or {})
            item_order[category] = order
            account.item_order = item_order
            account.save(update_fields=['item_order'])
        return JsonResponse({'category': category, 'order': order})


class ResetLayoutPreferencesView(LoginRequiredMixin, View):
    """Clears both saved layout preferences so a user can't get stuck after a
    confusing drag - back to the doc's default order."""

    def post(self, request):
        with transaction.atomic():
            account = Account.objects.select_for_update().get(pk=request.user.account_id)
            account.category_order = []
            account.item_order = {}
            account.save(update_fields=['category_order', 'item_order'])
        messages.success(request, 'Material list order reset to default.')
        return redirect('estimating:estimate-detail', pk=request.POST.get('estimate_id'))


class ManualLineItemCreateView(LoginRequiredMixin, View):
    def post(self, request, estimate_id):
        estimate = get_object_or_404(Estimate.objects.for_account(request.user.account), pk=estimate_id)
        form = ManualLineItemForm(request.POST, account=request.user.account)
        if form.is_valid():
            line_item = form.save(commit=False)
            line_item.estimate = estimate
            line_item.source = LineItem.Source.MANUAL
            line_item.save()
            messages.success(request, f'Added {line_item.quantity} x {line_item.material.name}.')
        else:
            errors = '; '.join(
                f'{field}: {", ".join(field_errors)}' for field, field_errors in form.errors.items()
            )
            messages.error(request, f'Could not add line: {errors}')
        return redirect('estimating:estimate-detail', pk=estimate.pk)


class ManualLineItemDeleteView(LoginRequiredMixin, View):
    """Manual lines only. Tool-generated lines are owned by their trace - they
    would silently reappear on the next regeneration, so deleting them here
    would be misleading. Remove those by deleting or editing the trace."""

    def post(self, request, pk):
        line_item = get_object_or_404(
            LineItem.objects.filter(
                estimate__project__account=request.user.account,
                source=LineItem.Source.MANUAL,
            ),
            pk=pk,
        )
        estimate_id = line_item.estimate_id
        line_item.delete()
        messages.success(request, 'Line removed.')
        return redirect('estimating:estimate-detail', pk=estimate_id)


class LibraryView(LoginRequiredMixin, TemplateView):
    template_name = 'estimating/library.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = self.request.user.account
        context['formulas'] = Formula.objects.visible_to(account).select_related('base_formula')
        context['assemblies'] = (
            Assembly.objects.visible_to(account)
            .prefetch_related('rules__material', 'rules__formula')
            .order_by('tool_type', 'name')
        )
        return context


class FormulaCreateView(LoginRequiredMixin, CreateView):
    form_class = FormulaForm
    template_name = 'estimating/formula_form.html'
    success_url = reverse_lazy('estimating:library')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['account'] = self.request.user.account
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f'Formula “{form.cleaned_data["name"]}” created.')
        return super().form_valid(form)


class AssemblyCreateView(LoginRequiredMixin, View):
    template_name = 'estimating/assembly_form.html'

    def get(self, request):
        assembly = Assembly(account=request.user.account)
        return self._render(request, AssemblyForm(instance=assembly), CalculationRuleFormSet(
            instance=assembly, form_kwargs={'account': request.user.account},
        ))

    def post(self, request):
        assembly = Assembly(account=request.user.account)
        form = AssemblyForm(request.POST, instance=assembly)
        rules = CalculationRuleFormSet(
            request.POST, instance=assembly, form_kwargs={'account': request.user.account},
        )
        if form.is_valid() and rules.is_valid():
            with transaction.atomic():
                assembly = form.save()
                rules.instance = assembly
                rules.save()
            messages.success(request, f'Assembly “{assembly.name}” created.')
            return redirect('estimating:library')
        return self._render(request, form, rules)

    def _render(self, request, form, rules):
        return render(request, self.template_name, {'form': form, 'rules': rules})
