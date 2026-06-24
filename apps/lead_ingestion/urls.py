from django.urls import path
from lead_ingestion import views
from lead_ingestion import views_ui

app_name = 'lead_ingestion'

urlpatterns = [
    # API endpoints
    path('api/v1/leads/webhook/', views.WebhookIngestionView.as_view(), name='webhook_ingestion'),
    path('api/v1/leads/webhook/<str:source>/', views.WebhookIngestionView.as_view(), name='webhook_ingestion_with_source'),
    path('api/v1/leads/form/', views.FormIngestionView.as_view(), name='form_ingestion'),
    path('api/v1/leads/upload/', views.CSVIngestionView.as_view(), name='csv_ingestion'),

    # UI views
    path('leads/', views_ui.dashboard, name='dashboard'),
    path('leads/raw/', views_ui.raw_lead_list, name='raw_lead_list'),
    path('leads/raw/<int:pk>/', views_ui.raw_lead_detail, name='raw_lead_detail'),
    path('leads/parsed/', views_ui.parsed_lead_list, name='parsed_lead_list'),
    path('leads/parsed/<int:pk>/', views_ui.parsed_lead_detail, name='parsed_lead_detail'),
    path('leads/upload/', views_ui.upload_csv, name='upload_csv'),
    path('leads/config/', views_ui.config_view, name='config'),
    path('leads/failed/', views_ui.failed_leads, name='failed_leads'),
    path('leads/failed/<int:pk>/requeue/', views_ui.requeue_lead, name='requeue_lead'),
    path('leads/export/', views_ui.export_leads, name='export_leads'),
    path('leads/parsed/<int:pk>/move_to_crm/', views_ui.move_to_crm, name='move_to_crm'),
    path('leads/raw/<int:pk>/delete/', views_ui.delete_raw_lead, name='delete_raw_lead'),
    path('leads/parsed/<int:pk>/delete/', views_ui.delete_parsed_lead, name='delete_parsed_lead'),
]
