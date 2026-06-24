from django.contrib import admin
from .models import Role, Permission, Team, AuditLog


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display  = ('name', 'is_system', 'created_at')
    list_filter   = ('is_system',)
    search_fields = ('name',)
    readonly_fields = ('created_at',)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display  = ('role', 'module', 'action', 'scope')
    list_filter   = ('role', 'module', 'scope')
    search_fields = ('role__name',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display  = ('name', 'organization', 'manager', 'created_at')
    list_filter   = ('organization',)
    search_fields = ('name',)
    autocomplete_fields = ('manager',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ('timestamp', 'user', 'user_role', 'action_type', 'module',
                     'affected_record_id', 'ip_address', 'success')
    list_filter   = ('action_type', 'module', 'success')
    search_fields = ('user__username', 'user__email', 'affected_record_id')
    readonly_fields = tuple(f.name for f in AuditLog._meta.get_fields())
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
