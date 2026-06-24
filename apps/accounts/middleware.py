"""
Organization Middleware.

Attaches `request.organization` and `request.org_user_ids` to every
authenticated request so views can filter data at the org level instead
of the individual user level.

Usage in views:
    # Old (single-user):
    campaigns = BdrCampaign.objects.filter(user=request.user)

    # New (org-level):
    campaigns = BdrCampaign.objects.filter(user_id__in=request.org_user_ids)
"""

import logging

logger = logging.getLogger(__name__)


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._attach_org(request)
        return self.get_response(request)

    def _attach_org(self, request):
        """Resolve the organization and user ID list for the current request."""
        request.organization = None
        request.org_user_ids = []

        if not request.user.is_authenticated:
            return

        try:
            profile = request.user.profile
            org = profile.organization

            if org and org.is_active:
                request.organization = org
                request.org_user_ids = org.get_user_ids()
            else:
                # No org yet (legacy user) — fall back to single-user isolation
                request.org_user_ids = [request.user.id]

        except Exception as exc:
            # Profile may not exist yet (e.g. admin users) — safe fallback
            logger.debug(f"OrganizationMiddleware fallback for {request.user}: {exc}")
            request.org_user_ids = [request.user.id]
