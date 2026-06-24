from rest_framework import authentication
from rest_framework import exceptions
from lead_ingestion.models import TenantIngestionConfig


class TenantAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    Custom DRF authentication backend that validates the X-Agentyne-Api-Key header.
    Supports hashed API keys via TenantIngestionConfig.verify_api_key().
    Returns (tenant_owner_user, ingestion_config).
    Also sets request.organization to the authenticated tenant (Organization).
    """
    def authenticate(self, request):
        # 1. Try Header
        api_key = request.headers.get('X-Agentyne-Api-Key')
        
        # 2. Try Query Params (For Meta webhooks)
        if not api_key:
            api_key = request.query_params.get('hub.verify_token') or request.query_params.get('api_key')

        if not api_key:
            return None

        configs = TenantIngestionConfig.objects.select_related(
            'tenant', 'tenant__owner'
        ).filter(is_active=True)

        config = None
        for cfg in configs:
            if cfg.verify_api_key(api_key):
                config = cfg
                break

        if config is None:
            raise exceptions.AuthenticationFailed('Invalid or inactive API Key.')

        request.organization = config.tenant
        return (config.tenant.owner, config)

    def authenticate_header(self, request):
        return 'ApiKey realm="api"'
