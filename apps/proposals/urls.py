"""
URL configuration for the Proposals module.

All URLs are under the /proposals/ prefix (configured in asoc_core/urls.py).
"""
from django.urls import path
from proposals.views import wizard, editor, brand, settings as settings_views, export, api

app_name = 'proposals'

urlpatterns = [
    # ── Document List (landing page) ────────────────────────────────────────
    path('', wizard.document_list, name='document_list'),

    # ── Wizard (multi-step intake) ──────────────────────────────────────────
    path('create/', wizard.wizard_start, name='wizard_start'),
    path('create/step/<int:step>/', wizard.wizard_step, name='wizard_step'),
    path('create/step/<int:step>/save/', wizard.wizard_save_step, name='wizard_save_step'),
    path('create/generate/', wizard.wizard_generate, name='wizard_generate'),

    # ── Document Editor ─────────────────────────────────────────────────────
    path('<int:doc_id>/edit/', editor.document_editor, name='document_editor'),
    path('<int:doc_id>/delete/', editor.document_delete, name='document_delete'),
    path('<int:doc_id>/section/<int:section_id>/save/', editor.section_save, name='section_save'),
    path('<int:doc_id>/section/<int:section_id>/regenerate/', editor.section_regenerate, name='section_regenerate'),
    path('<int:doc_id>/section/reorder/', editor.section_reorder, name='section_reorder'),
    path('<int:doc_id>/section/save-all/', editor.save_all_sections, name='save_all_sections'),

    # ── Export ──────────────────────────────────────────────────────────────
    path('<int:doc_id>/export/docx/', export.export_docx, name='export_docx'),
    path('<int:doc_id>/export/pdf/', export.export_pdf, name='export_pdf'),

    # ── Brand Guidelines ────────────────────────────────────────────────────
    path('brands/', brand.brand_list, name='brand_list'),
    path('brands/create/', brand.brand_create, name='brand_create'),
    path('brands/<int:brand_id>/edit/', brand.brand_edit, name='brand_edit'),
    path('brands/<int:brand_id>/delete/', brand.brand_delete, name='brand_delete'),
    path('brands/<int:brand_id>/preview/', brand.brand_preview, name='brand_preview'),

    # ── Settings ────────────────────────────────────────────────────────────
    path('settings/', settings_views.proposal_settings, name='proposal_settings'),

    # ── API / HTMX endpoints ────────────────────────────────────────────────
    path('api/generate-questions/', api.generate_questions, name='api_generate_questions'),
    path('api/job-status/<int:job_id>/', api.job_status, name='api_job_status'),
    path('api/generate-image/', api.generate_image_api, name='api_generate_image'),
    path('<int:doc_id>/api/autosave/', api.autosave, name='api_autosave'),
]
