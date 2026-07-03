from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from .forms import ProjectForm
from .models import JobSettings, Project


class DashboardView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'projects/dashboard.html'
    context_object_name = 'projects'

    def get_queryset(self):
        return Project.objects.for_account(self.request.user.account).exclude(
            status=Project.Status.ARCHIVED,
        )


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'

    def form_valid(self, form):
        form.instance.account = self.request.user.account
        response = super().form_valid(form)
        JobSettings.objects.create(project=self.object)
        return response

    def get_success_url(self):
        return reverse('projects:detail', args=[self.object.pk])


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'

    def get_queryset(self):
        return Project.objects.for_account(self.request.user.account)
