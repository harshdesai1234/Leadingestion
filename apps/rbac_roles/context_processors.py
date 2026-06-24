"""
RBAC context processor — injects user's role info into every template.
"""


def rbac_context(request):
    """
    Adds to every template context:
      - user_rbac_role  : the Role instance (or None)
      - is_admin_user   : True if Super Admin or Admin
    """
    if not request.user.is_authenticated:
        return {'user_rbac_role': None, 'is_admin_user': False}

    try:
        role = request.user.profile.rbac_role
    except Exception:
        role = None

    is_admin = False
    if role:
        from rbac_roles.models import ROLE_SUPER_ADMIN, ROLE_ADMIN
        is_admin = role.name in (ROLE_SUPER_ADMIN, ROLE_ADMIN)

    return {
        'user_rbac_role': role,
        'is_admin_user': is_admin,
    }
