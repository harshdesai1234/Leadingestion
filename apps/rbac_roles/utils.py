"""
RBAC Permission Utilities
=========================
Provides helpers for checking permissions, scoping querysets, and
logging audit events.  Import these in views and APIs.

Usage example:
    from rbac_roles.utils import require_permission, get_scoped_queryset, log_audit

    @login_required
    @require_permission('leads', 'read')
    def lead_list(request):
        qs = get_scoped_queryset(request, Lead, 'leads')
        ...
"""
from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import render

from .models import Permission, Scope, AuditLog


# ─────────────────────────────────────────────────────────────────────────────
# Helpers to fetch the user's role / permissions
# ─────────────────────────────────────────────────────────────────────────────

def get_user_role(user):
    """Return the Role instance attached to the user, or None."""
    try:
        return user.profile.rbac_role
    except Exception:
        return None


def get_user_scope(user, module, action):
    """
    Return the Scope string (e.g. 'own', 'team', 'all', 'none') for the
    given user/module/action combination.

    Falls back to 'none' when no permission row exists.
    """
    # Django superusers always have full access regardless of RBAC role
    if getattr(user, 'is_superuser', False):
        return Scope.ALL

    role = get_user_role(user)
    if role is None:
        # Users with no RBAC role get own-scope access as a safe default
        return Scope.OWN

    # Super-admin short-circuit
    from .models import ROLE_SUPER_ADMIN
    if role.name == ROLE_SUPER_ADMIN:
        return Scope.ALL

    try:
        perm = Permission.objects.get(role=role, module=module, action=action)
        return perm.scope
    except Permission.DoesNotExist:
        return Scope.NONE


def has_permission(user, module, action):
    """Return True if the user has any access (scope != 'none') for module/action."""
    return get_user_scope(user, module, action) != Scope.NONE


def is_admin_or_super(user):
    """
    Return True if the user holds the 'Super Admin' or 'Admin' role.
    Used to gate privileged actions like inviting users, managing teams, etc.
    """
    from .models import ROLE_SUPER_ADMIN, ROLE_ADMIN
    role = get_user_role(user)
    if role is None:
        return False
    return role.name in (ROLE_SUPER_ADMIN, ROLE_ADMIN)


def require_admin_role(view_func):
    """
    Decorator: only Super Admin and Admin can access the view.
    Returns 403 for all other roles.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as _settings
            from django.shortcuts import redirect
            return redirect(_settings.LOGIN_URL)
        if not is_admin_or_super(request.user):
            log_audit(
                request=request,
                action_type='access_denied',
                module='settings',
                extra={'attempted_action': 'invite_user'},
                success=False,
            )
            return render(request, 'rbac_roles/403.html', status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped

# ─────────────────────────────────────────────────────────────────────────────
# Row-level (queryset) scoping
# ─────────────────────────────────────────────────────────────────────────────

def get_scoped_queryset(request, queryset, module, action='read'):
    """
    Filter *queryset* according to the user's data-level scope.

    The queryset model must have at least one of these FK fields for scoping
    to work:
      - `owner`      → filters by owner=request.user
      - `created_by` → used as fallback if no owner field
      - `owner__profile__team`  → for team-level scope (Sales Manager)

    Returns the filtered queryset (or .none() on scope='none').
    """
    user  = request.user
    scope = get_user_scope(user, module, action)
    model_fields = {f.name for f in queryset.model._meta.get_fields()}

    if scope == Scope.NONE:
        return queryset.none()

    if scope == Scope.ALL:
        return queryset

    if scope == Scope.OWN:
        if 'owner' in model_fields:
            return queryset.filter(owner=user)
        if 'created_by' in model_fields:
            return queryset.filter(created_by=user)
        # Fallback: user has no ownership field → empty
        return queryset.none()

    if scope == Scope.TEAM:
        user_teams = getattr(getattr(user, 'profile', None), 'teams', None)
        if user_teams is None:
            return queryset.none()
        team_ids = list(user_teams.values_list('id', flat=True))
        if not team_ids:
            return queryset.none()
        # Leads/Opportunities: owner's profile must share a team with the manager
        if 'owner' in model_fields:
            return queryset.filter(owner__profile__teams__in=team_ids).distinct()
        if 'created_by' in model_fields:
            return queryset.filter(created_by__profile__teams__in=team_ids).distinct()
        return queryset.none()

    return queryset


def mask_financial_fields(obj_or_dict, user, fields=None):
    """
    Zero-out / None-out financial fields for roles that lack financial visibility.

    Roles with financial access (per spec): Super Admin, Sales Manager (team),
    Read-Only, Marketing Manager (campaigns only).
    Pass a dict or model instance; receives the same type back.
    """
    FINANCIAL_ROLES = {'Super Admin', 'Sales Manager', 'Read-Only', 'Marketing Manager'}
    role = get_user_role(user)
    role_name = role.name if role else ''

    if role_name in FINANCIAL_ROLES:
        return obj_or_dict

    default_financial_fields = fields or [
        'amount', 'deal_value', 'expected_revenue', 'campaign_budget',
        'budget', 'revenue', 'price',
    ]

    if isinstance(obj_or_dict, dict):
        for field in default_financial_fields:
            if field in obj_or_dict:
                obj_or_dict[field] = None
    else:
        for field in default_financial_fields:
            if hasattr(obj_or_dict, field):
                setattr(obj_or_dict, field, None)

    return obj_or_dict


# ─────────────────────────────────────────────────────────────────────────────
# View Decorator
# ─────────────────────────────────────────────────────────────────────────────

def require_permission(module, action):
    """
    Decorator for Django views.  Returns 403 if the user's role
    does not permit the action on the given module.

    Usage:
        @login_required
        @require_permission('leads', 'create')
        def lead_create(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.conf import settings as _settings
                from django.shortcuts import redirect
                return redirect(_settings.LOGIN_URL)

            if not has_permission(request.user, module, action):
                # Log the denied attempt
                log_audit(
                    request=request,
                    action_type='access_denied',
                    module=module,
                    extra={'attempted_action': action},
                    success=False,
                )
                return render(request, 'rbac_roles/403.html', status=403)

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Audit logging helper
# ─────────────────────────────────────────────────────────────────────────────

def log_audit(request, action_type, module='', affected_record_id='',
              extra=None, success=True):
    """
    Create an AuditLog entry.  Safe to call from anywhere.

    :param request: Django request object (for user, IP).
    :param action_type: One of AuditLog.ACTION_TYPES keys.
    :param module: Module name string.
    :param affected_record_id: PK or identifier of the affected record.
    :param extra: Dict of additional data (before/after values, counts, etc.)
    :param success: Whether the action succeeded.
    """
    user = request.user if request and request.user.is_authenticated else None
    ip   = _get_client_ip(request) if request else None
    role = get_user_role(user) if user else None

    try:
        AuditLog.objects.create(
            user=user,
            user_role=role.name if role else '',
            action_type=action_type,
            module=module,
            affected_record_id=str(affected_record_id),
            extra_data=extra or {},
            ip_address=ip,
            success=success,
        )
    except Exception:
        # Never let logging break the main flow
        pass


def _get_client_ip(request):
    """Extract the real client IP from the request."""
    if not request:
        return None
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
