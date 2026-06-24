"""
Permission utilities for the Proposals module.

Integrates with the existing rbac_roles system by checking the user's RBAC
permissions for the 'proposals' module. Provides a decorator and a mixin
for view-level permission checks.
"""
from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required


# ── Permission Codenames ────────────────────────────────────────────────────
PROPOSAL_PERMISSIONS = [
    ('proposals.view_document', 'Can view proposals'),
    ('proposals.create_document', 'Can create proposals'),
    ('proposals.edit_document', 'Can edit proposals'),
    ('proposals.delete_document', 'Can delete proposals'),
    ('proposals.export_document', 'Can export proposals'),
    ('proposals.manage_brand', 'Can manage brand guidelines'),
    ('proposals.manage_settings', 'Can manage proposal module settings'),
    ('proposals.view_all', 'Can view all org proposals (manager)'),
]


def _get_user_rbac_scope(user, module, action):
    """
    Check the user's RBAC scope for a given module + action.

    Returns the scope string ('none', 'own', 'team', 'all') or 'none' if
    no permission is found. Integrates with rbac_roles.Permission model.
    """
    try:
        from rbac_roles.models import Permission as RBACPermission
        profile = getattr(user, 'profile', None)
        if not profile or not profile.rbac_role:
            # No RBAC role assigned — fall back to legacy role check
            # Owners and admins get full access
            if profile and profile.role in ('owner', 'admin', 'superadmin'):
                return 'all'
            return 'own'  # Default: users can access their own records

        perm = RBACPermission.objects.filter(
            role=profile.rbac_role,
            module=module,
            action=action,
        ).first()
        return perm.scope if perm else 'own'
    except Exception:
        # If RBAC system is unavailable, default to own-record access
        return 'own'


def get_proposal_scope(user, action='read'):
    """Get the user's scope for the proposals module."""
    return _get_user_rbac_scope(user, 'proposals', action)


def has_proposal_permission(user, action='read'):
    """Check if user has any non-none access to proposals for the given action."""
    scope = get_proposal_scope(user, action)
    return scope != 'none'


def proposal_permission_required(action='read'):
    """
    Decorator that checks the user's RBAC permission for the proposals module.
    Returns 403 if user has no access.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not has_proposal_permission(request.user, action):
                return HttpResponseForbidden(
                    '<h1>403 Forbidden</h1>'
                    '<p>You do not have permission to access this resource.</p>'
                )
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def filter_proposals_by_scope(queryset, user, scope=None):
    """
    Filter a proposals queryset based on the user's RBAC scope.

    - 'all'  → return all records for the user's organisation
    - 'team' → return records by team members (falls back to 'all' for now)
    - 'own'  → return only records created by or assigned to the user
    - 'none' → return empty queryset
    """
    if scope is None:
        scope = get_proposal_scope(user, 'read')

    if scope == 'none':
        return queryset.none()

    # Always filter by organisation first (tenant isolation)
    org = getattr(getattr(user, 'profile', None), 'organization', None)
    if org:
        queryset = queryset.filter(organisation=org)
    else:
        return queryset.none()

    if scope == 'all':
        return queryset
    elif scope == 'team':
        # For team scope, include records from team members
        # Falls back to 'all' within org for simplicity (team filtering
        # can be refined when the team system is fully integrated)
        return queryset
    elif scope == 'own':
        from django.db.models import Q
        return queryset.filter(
            Q(created_by=user) | Q(assigned_to=user)
        )

    return queryset.none()
