from django.urls import path

from . import views

app_name = 'plans'

urlpatterns = [
    path('projects/<int:project_id>/upload/', views.PlanUploadView.as_view(), name='upload'),
    path('pages/<int:pk>/', views.PlanViewerView.as_view(), name='viewer'),
    path('pages/<int:pk>/label/', views.PlanPageLabelUpdateView.as_view(), name='page-label'),
    path('pages/<int:pk>/delete/', views.PlanPageDeleteView.as_view(), name='page-delete'),
    path('pages/<int:pk>/calibrate/', views.PlanPageCalibrateView.as_view(), name='page-calibrate'),
    path('pages/<int:page_id>/traces/', views.TraceCreateView.as_view(), name='trace-create'),
    path('traces/batch-update/', views.TraceBatchUpdateView.as_view(), name='trace-batch-update'),
    path('traces/batch-delete/', views.TraceBatchDeleteView.as_view(), name='trace-batch-delete'),
    path('traces/<int:pk>/update/', views.TraceUpdateView.as_view(), name='trace-update'),
    path('traces/<int:pk>/wall-elevation/', views.WallElevationView.as_view(), name='wall-elevation'),
    path('traces/<int:pk>/delete/', views.TraceDeleteView.as_view(), name='trace-delete'),
    path('presets/', views.ToolPresetListCreateView.as_view(), name='presets'),
]
