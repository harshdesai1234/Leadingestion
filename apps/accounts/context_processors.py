"""
accounts/context_processors.py
-------------------------------
Injects AI Receptionist credit warning into every template context.

Shows a topbar warning banner when:
  1. The org has at least one active AI Receptionist configured, AND
  2. Their remaining credits fall below AI_REC_LOW_CREDIT_THRESHOLD (default: 100)
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Credits below this level trigger the warning banner.
LOW_CREDIT_THRESHOLD = getattr(settings, 'AI_REC_LOW_CREDIT_THRESHOLD', 100)


def ai_rec_credit_context(request):
    """
    Context keys injected:
      - ai_rec_credit_warning  : True when warning should be shown
      - ai_rec_remaining_credits: int remaining credits (only set when warning is active)
    """
    if not request.user.is_authenticated:
        return {}

    try:
        org = getattr(request, 'organization', None)
        if not org:
            return {}

        from accounts.credit_service import get_credit_account
        account = get_credit_account(org)
        if account is None:
            return {}

        remaining = account.remaining_credits
        if remaining >= LOW_CREDIT_THRESHOLD:
            return {}

        # Only show warning when org has at least one active AI Receptionist
        org_user_ids = getattr(request, 'org_user_ids', [request.user.id])
        from ai_receptionist.models import AIReceptionist
        has_active = AIReceptionist.objects.filter(
            user_id__in=org_user_ids,
            is_active=True,
        ).exists()

        if has_active:
            return {
                'ai_rec_credit_warning': True,
                'ai_rec_remaining_credits': remaining,
            }

    except Exception as exc:
        logger.debug(f"ai_rec_credit_context error: {exc}")

    return {}
