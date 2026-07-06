from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView

from .forms import JobSettingsForm, ProjectSetupForm, ProjectTemplateForm
from .models import JobSettings, Project, ProjectTemplate


def _project_workflow_state(project):
    if not project.has_pages:
        return {
            'label': 'No plans uploaded',
            'tone': 'archived',
            'hint': 'Upload a PDF or image to start this takeoff.',
        }
    if project.has_uncalibrated_pages:
        return {
            'label': 'Needs calibration',
            'tone': 'warning',
            'hint': 'Open the plan and set the page scale before assigning assemblies.',
        }
    if project.has_line_items:
        return {
            'label': 'Estimate ready',
            'tone': 'active',
            'hint': 'Material quantities have been generated for this job.',
        }
    if project.has_traces:
        return {
            'label': 'Tracing in progress',
            'tone': 'info',
            'hint': 'Continue tracing to finish the material list.',
        }
    return {
        'label': 'Ready to trace',
        'tone': 'info',
        'hint': 'Plans are uploaded and calibrated. Start drawing takeoff items.',
    }


class StartTakeoffView(LoginRequiredMixin, View):
    """One-click entry into tracing. Sends the user to the page they last
    worked on (the page of the project's most recent trace), falling back to
    the first page of the newest plan, or back to the project with a prompt
    when nothing is uploaded yet. Turns dashboard-to-canvas into one click."""

    def get(self, request, pk):
        from plans.models import PlanPage, Trace

        project = get_object_or_404(Project.objects.for_account(request.user.account), pk=pk)

        last_trace = (
            Trace.objects.filter(plan_page__plan__project=project)
            .order_by('-created_at')
            .select_related('plan_page')
            .first()
        )
        if last_trace is not None:
            return redirect('plans:viewer', pk=last_trace.plan_page_id)

        first_page = (
            PlanPage.objects.filter(plan__project=project)
            .order_by('-plan__uploaded_at', 'page_number')
            .first()
        )
        if first_page is not None:
            return redirect('plans:viewer', pk=first_page.pk)

        messages.info(request, 'Upload a plan first, then start your takeoff.')
        return redirect('projects:detail', pk=project.pk)


class DashboardView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'projects/dashboard.html'
    context_object_name = 'projects'

    def get_queryset(self):
        from estimating.models import LineItem
        from plans.models import PlanPage, Trace

        return Project.objects.for_account(self.request.user.account).exclude(
            status=Project.Status.ARCHIVED,
        ).annotate(
            has_pages=Exists(PlanPage.objects.filter(plan__project=OuterRef('pk'))),
            has_uncalibrated_pages=Exists(
                PlanPage.objects.filter(plan__project=OuterRef('pk'), scale_pixels_per_foot__isnull=True)
            ),
            has_traces=Exists(Trace.objects.filter(plan_page__plan__project=OuterRef('pk'))),
            has_line_items=Exists(LineItem.objects.filter(estimate__project=OuterRef('pk'))),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_projects = Project.objects.for_account(self.request.user.account)
        context['active_count'] = all_projects.filter(status=Project.Status.ACTIVE).count()
        context['archived_count'] = all_projects.filter(status=Project.Status.ARCHIVED).count()
        context['total_count'] = all_projects.count()
        for project in context['projects']:
            workflow = _project_workflow_state(project)
            project.workflow_label = workflow['label']
            project.workflow_tone = workflow['tone']
            project.workflow_hint = workflow['hint']
        return context


class ProjectCreateView(LoginRequiredMixin, FormView):
    """The Project Setup Wizard: name/client, structure, and framing questions
    in one stepped form. Creates the Project + JobSettings + first Estimate."""

    form_class = ProjectSetupForm
    template_name = 'projects/project_form.html'

    def get_template_object(self):
        template_id = self.request.GET.get('template') or self.request.POST.get('template')
        if not template_id:
            return None
        return ProjectTemplate.objects.visible_to(self.request.user.account).filter(pk=template_id).first()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['account'] = self.request.user.account
        kwargs['template'] = self.get_template_object()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project_templates'] = ProjectTemplate.objects.visible_to(self.request.user.account)
        context['selected_template'] = self.get_template_object()
        return context

    def form_valid(self, form):
        self.object = form.save_with_settings(self.request.user.account)
        messages.success(self.request, f'{self.object.name} created. Upload a plan to start tracing.')
        return redirect('projects:detail', pk=self.object.pk)


class JobSettingsUpdateView(LoginRequiredMixin, UpdateView):
    """Edit a project's Job Settings after creation. Changing these does not
    retroactively recompute already-drawn traces (documented behavior) - new
    and re-saved traces pick up the new defaults."""

    form_class = JobSettingsForm
    template_name = 'projects/job_settings_form.html'
    context_object_name = 'job_settings'

    def get_object(self, queryset=None):
        project = get_object_or_404(
            Project.objects.for_account(self.request.user.account),
            pk=self.kwargs['pk'],
        )
        job_settings, _ = JobSettings.objects.get_or_create(project=project)
        return job_settings

    def form_valid(self, form):
        messages.success(self.request, 'Job settings saved. Newly drawn traces will use them as defaults.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('projects:detail', args=[self.object.project_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['save_template_url'] = f"{reverse('projects:template-create')}?source_project={self.object.project_id}"
        return context


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'

    def get_queryset(self):
        return Project.objects.for_account(self.request.user.account)


class ProjectTemplateMixin(LoginRequiredMixin):
    model = ProjectTemplate

    def get_queryset(self):
        return ProjectTemplate.objects.filter(account=self.request.user.account)


class ProjectTemplateListView(LoginRequiredMixin, ListView):
    model = ProjectTemplate
    template_name = 'projects/template_library.html'
    context_object_name = 'templates'

    def get_queryset(self):
        account = self.request.user.account
        return ProjectTemplate.objects.visible_to(account).order_by('account_id', 'sort_order', 'name')


class ProjectTemplateCreateView(LoginRequiredMixin, CreateView):
    model = ProjectTemplate
    form_class = ProjectTemplateForm
    template_name = 'projects/template_form.html'

    def get_initial(self):
        initial = super().get_initial()
        source_project_id = self.request.GET.get('source_project')
        if not source_project_id:
            return initial
        project = get_object_or_404(Project.objects.for_account(self.request.user.account), pk=source_project_id)
        job_settings = getattr(project, 'job_settings', None)
        if job_settings is None:
            return initial
        initial.update(ProjectTemplate.from_job_settings(job_settings).to_form_initial())
        initial['name'] = f'{project.name} Template'
        initial['description'] = f'Reusable defaults from {project.name}.'
        initial.pop('template', None)
        return initial

    def form_valid(self, form):
        form.instance.account = self.request.user.account
        messages.success(self.request, f'Project template "{form.instance.name}" saved.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('projects:template-library')


class ProjectTemplateUpdateView(ProjectTemplateMixin, UpdateView):
    form_class = ProjectTemplateForm
    template_name = 'projects/template_form.html'
    context_object_name = 'project_template'

    def form_valid(self, form):
        messages.success(self.request, f'Project template "{form.instance.name}" updated.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('projects:template-library')


class ProjectTemplateDeleteView(ProjectTemplateMixin, DeleteView):
    template_name = 'projects/template_confirm_delete.html'
    context_object_name = 'project_template'

    def post(self, request, *args, **kwargs):
        messages.success(request, 'Project template deleted.')
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('projects:template-library')
