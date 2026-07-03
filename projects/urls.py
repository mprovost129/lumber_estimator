from django.urls import path

from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('new/', views.ProjectCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='detail'),
]
