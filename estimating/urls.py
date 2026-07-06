from django.urls import path

from . import views

app_name = 'estimating'

urlpatterns = [
    path('library/', views.LibraryView.as_view(), name='library'),
    path('library/formulas/new/', views.FormulaCreateView.as_view(), name='formula-create'),
    path('library/assemblies/new/', views.AssemblyCreateView.as_view(), name='assembly-create'),
    path(
        'library/assemblies/<int:pk>/quick-edit/', views.AssemblyQuickEditView.as_view(),
        name='assembly-quick-edit',
    ),
    path('estimates/<int:pk>/', views.EstimateDetailView.as_view(), name='estimate-detail'),
    path(
        'estimates/<int:pk>/material-summary/', views.EstimateMaterialSummaryView.as_view(),
        name='estimate-material-summary',
    ),
    path('estimates/<int:pk>/print/', views.EstimatePrintView.as_view(), name='estimate-print'),
    path('estimates/<int:pk>/export.csv', views.EstimateCsvExportView.as_view(), name='estimate-csv'),
    path('estimates/<int:estimate_id>/lines/add/', views.ManualLineItemCreateView.as_view(), name='line-item-add'),
    path('lines/<int:pk>/delete/', views.ManualLineItemDeleteView.as_view(), name='line-item-delete'),
    path(
        'preferences/category-order/', views.CategoryOrderUpdateView.as_view(),
        name='category-order-update',
    ),
    path('preferences/item-order/', views.ItemOrderUpdateView.as_view(), name='item-order-update'),
    path(
        'preferences/reset/', views.ResetLayoutPreferencesView.as_view(),
        name='reset-layout-preferences',
    ),
]
