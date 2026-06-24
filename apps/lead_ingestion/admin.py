from django.contrib import admin
from lead_ingestion.models import RawLead, ParsedLead, TenantIngestionConfig


@admin.register(TenantIngestionConfig)
class TenantIngestionConfigAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'api_key_short', 'is_active', 'batch_minutes', 'default_action']
    list_filter = ['is_active', 'default_action']
    search_fields = ['tenant__name', 'api_key']
    readonly_fields = ['api_key']

    def api_key_short(self, obj):
        return f"{obj.api_key[:12]}..."
    api_key_short.short_description = "API Key"


@admin.register(RawLead)
class RawLeadAdmin(admin.ModelAdmin):
    list_display = ['id', 'tenant', 'source_hint', 'status', 'retry_count', 'received_at', 'processed_at']
    list_filter = ['status', 'source_hint', 'tenant']
    search_fields = ['tenant__name', 'payload']
    readonly_fields = ['received_at', 'processed_at']
    date_hierarchy = 'received_at'


@admin.register(ParsedLead)
class ParsedLeadAdmin(admin.ModelAdmin):
    list_display = ['id', 'tenant', 'customer_name', 'email_address', 'mobile_number', 'source', 'predefined_action', 'created_at']
    list_filter = ['source', 'predefined_action', 'tenant']
    search_fields = ['customer_name', 'email_address', 'mobile_number']
    readonly_fields = ['created_at']
