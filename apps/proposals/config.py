"""
Centralized configuration for the Proposals module.

All module config lives here, reading from Django settings with safe defaults.
This ensures the module is self-contained and never hardcodes host-project values.
"""
import os
from django.conf import settings


PROPOSALS_CONFIG = {
    # Tenant model path (used for dynamic FK resolution if needed)
    'TENANT_MODEL': getattr(settings, 'PROPOSALS_TENANT_MODEL', 'accounts.Organization'),

    # The FK field name on the tenant model used for filtering
    'TENANT_FK_FIELD': getattr(settings, 'PROPOSALS_TENANT_FK', 'organisation'),

    # Media subdirectory for proposal assets
    'MEDIA_SUBDIR': getattr(settings, 'PROPOSALS_MEDIA_SUBDIR', 'proposals/'),

    # Default AI models
    'DEFAULT_TEXT_MODEL': getattr(settings, 'PROPOSALS_DEFAULT_TEXT_MODEL', 'claude-sonnet-4-6'),
    'DEFAULT_IMAGE_MODEL': getattr(settings, 'PROPOSALS_DEFAULT_IMAGE_MODEL', 'imagen-3.0-generate-002'),

    # Celery toggle — if False, AI generation runs synchronously
    'ENABLE_CELERY': getattr(settings, 'PROPOSALS_ENABLE_CELERY', False),

    # Base template to extend (the host project's layout)
    'BASE_TEMPLATE': getattr(settings, 'PROPOSALS_BASE_TEMPLATE', 'dashboard/base.html'),

    # Maximum tokens per AI generation call
    # Claude Sonnet 4.6 supports up to 8192 output tokens — use 8000 for safety headroom
    'MAX_TOKENS_PER_GENERATION': getattr(settings, 'PROPOSALS_MAX_TOKENS', 8000),

    # Phase 8 Section-by-Section Settings
    'PROPOSALS_MAX_SECTIONS': getattr(settings, 'PROPOSALS_MAX_SECTIONS', 40),
    'PROPOSALS_TOKENS_PER_SECTION': getattr(settings, 'PROPOSALS_TOKENS_PER_SECTION', 2000),
    'PROPOSALS_SECTION_SYNC_THRESHOLD': getattr(settings, 'PROPOSALS_SECTION_SYNC_THRESHOLD', 8),
}

# Keys that must be read live (not cached at import time) so that values set
# in .env after the module was first imported are still picked up correctly.
_LIVE_KEYS = {'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY', 'OPENAI_API_KEY'}


def get_config(key):
    """Retrieve a config value by key.

    For API keys, always reads from Django settings first, then falls back to
    os.environ directly so that .env values loaded by load_dotenv() are always
    visible regardless of module import order.
    """
    if key in _LIVE_KEYS:
        # 1. Try Django settings (set via os.getenv in settings.py)
        value = getattr(settings, key, '') or ''
        # 2. Fall back to os.environ directly
        if not value:
            value = os.environ.get(key, '')
        return value
    return PROPOSALS_CONFIG.get(key)
