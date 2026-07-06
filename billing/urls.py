from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.BillingOverviewView.as_view(), name='overview'),
    path('estimate/<int:pk>/checkout/', views.EstimateCheckoutSessionCreateView.as_view(), name='estimate-checkout'),
    path('subscribe/<slug:slug>/', views.SubscriptionCheckoutSessionCreateView.as_view(), name='subscribe'),
    path('portal/', views.CustomerPortalLaunchView.as_view(), name='portal'),
    path('webhooks/stripe/', views.StripeWebhookView.as_view(), name='stripe-webhook'),
]

