"""
Role Capabilities view — shows the full permission matrix for all roles.
Accessible to Super Admin and Admin only.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rbac_roles.models import Role, Permission, Module, Action, Scope
from rbac_roles.utils import require_admin_role


SCOPE_LABELS = {
    Scope.ALL:  {'label': 'Full',  'color': '#10b981', 'icon': '✦'},
    Scope.TEAM: {'label': 'Team',  'color': '#f59e0b', 'icon': '◈'},
    Scope.OWN:  {'label': 'Own',   'color': '#3b82f6', 'icon': '●'},
    Scope.NONE: {'label': '—',     'color': '#d1d5db', 'icon': '—'},
}

# Ordered list of (module_key, display_name)
MODULES = [
    ('dashboard',      'Dashboard'),
    ('leads',          'Leads'),
    ('opportunities',  'Opportunities'),
    ('campaigns',      'Campaigns'),
    ('ai_agents',      'AI Agents'),
    ('settings',       'Settings'),
]

# Key actions we show in the matrix
ACTIONS = ['read', 'create', 'update', 'delete', 'export', 'publish']


@login_required
@require_admin_role
def role_capabilities(request):
    """Permission matrix: rows = roles, columns = modules, cells = scope per action."""
    roles = list(Role.objects.all().order_by('name').prefetch_related('permissions'))

    # Build a nested dict: perm_map[role_id][module][action] = scope_meta
    perm_map = {}
    for role in roles:
        perm_map[role.id] = {}
        for mod_key, _ in MODULES:
            perm_map[role.id][mod_key] = {}
            for action in ACTIONS:
                perm_map[role.id][mod_key][action] = SCOPE_LABELS[Scope.NONE]

        for perm in role.permissions.all():
            if perm.module in perm_map[role.id] and perm.action in ACTIONS:
                meta = SCOPE_LABELS.get(perm.scope, SCOPE_LABELS[Scope.NONE])
                perm_map[role.id][perm.module][perm.action] = meta

    return render(request, 'rbac_roles/role_capabilities.html', {
        'roles': roles,
        'modules': MODULES,
        'actions': ACTIONS,
        'perm_map': perm_map,
        'scope_labels': SCOPE_LABELS,
    })
