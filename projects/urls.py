from django.urls import path

from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('new/', views.ProjectCreateView.as_view(), name='create'),
    path('templates/', views.ProjectTemplateListView.as_view(), name='template-library'),
    path('templates/new/', views.ProjectTemplateCreateView.as_view(), name='template-create'),
    path('templates/<int:pk>/edit/', views.ProjectTemplateUpdateView.as_view(), name='template-update'),
    path('templates/<int:pk>/delete/', views.ProjectTemplateDeleteView.as_view(), name='template-delete'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='detail'),
    path('<int:pk>/takeoff/', views.StartTakeoffView.as_view(), name='start-takeoff'),
    path('<int:pk>/settings/', views.JobSettingsUpdateView.as_view(), name='job-settings'),
]
