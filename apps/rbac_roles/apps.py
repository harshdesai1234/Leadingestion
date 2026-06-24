from django.apps import AppConfig


class RbacRolesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rbac_roles'
    verbose_name = 'RBAC – Roles & Permissions'

    def ready(self):
        # Disable signals as we removed related apps
        pass
