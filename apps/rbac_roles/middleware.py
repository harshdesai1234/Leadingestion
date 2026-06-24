"""
RBAC Middleware
===============
Attaches the user's RBAC role to every request so templates/views
can access it via `request.rbac_role` and `request.rbac_role_name`.

Also re-evaluates role changes every request (not cached in JWT),
satisfying Spec §9.5 "Role Changes Take Effect Immediately".
"""
from .utils import get_user_role


class RBACMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            role = get_user_role(request.user)
            request.rbac_role = role
            request.rbac_role_name = role.name if role else ''
        else:
            request.rbac_role = None
            request.rbac_role_name = ''

        return self.get_response(request)
