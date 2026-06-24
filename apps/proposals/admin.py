"""
Django admin registration for the Proposals module.

All models are registered with sensible list displays and filters
for easy administration.
"""
from django.contrib import admin
from proposals.models import (
    BrandGuideline,
    Document,
    DocumentSection,
    Asset,
    AIJob,
    ModuleSettings,
)


@admin.register(BrandGuideline)
class BrandGuidelineAdmin(admin.ModelAdmin):
    list_display = ('name', 'organisation', 'primary_color', 'heading_font', 'is_default', 'updated_at')
    list_filter = ('is_default', 'organisation')
    search_fields = ('name', 'organisation__name')
    readonly_fields = ('created_at', 'updated_at')


class DocumentSectionInline(admin.TabularInline):
    model = DocumentSection
    extra = 0
    fields = ('order', 'section_type', 'title', 'is_visible', 'ai_generated')
    ordering = ('order',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'doc_type', 'status', 'organisation', 'created_by', 'version', 'updated_at')
    list_filter = ('doc_type', 'status', 'content_mode', 'organisation')
    search_fields = ('title', 'recipient_name', 'organisation__name')
    readonly_fields = ('created_at', 'updated_at', 'word_count')
    inlines = [DocumentSectionInline]


@admin.register(DocumentSection)
class DocumentSectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'document', 'section_type', 'order', 'is_visible', 'ai_generated')
    list_filter = ('section_type', 'is_visible', 'ai_generated')
    search_fields = ('title', 'document__title')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'asset_type', 'organisation', 'document', 'uploaded_by', 'created_at')
    list_filter = ('asset_type', 'organisation')
    search_fields = ('original_filename', 'description')
    readonly_fields = ('created_at',)


@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ('job_type', 'status', 'document', 'model_used', 'tokens_used', 'duration_seconds', 'created_at')
    list_filter = ('job_type', 'status', 'model_used')
    search_fields = ('document__title',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ModuleSettings)
class ModuleSettingsAdmin(admin.ModelAdmin):
    list_display = ('organisation', 'text_model_provider', 'text_model_name', 'image_model_provider', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
