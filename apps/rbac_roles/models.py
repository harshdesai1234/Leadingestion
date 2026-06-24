"""
RBAC Models for Agentyne ASOC.

Defines Roles, Permissions (per module/action/scope), Teams, and AuditLog.
UserProfile gains FK references to Role and Team via accounts/models.py.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# Module & Action Constants
# ─────────────────────────────────────────────────────────────────────────────
class Module(models.TextChoices):
    DASHBOARD   = 'dashboard',    'Dashboard'
    LEADS       = 'leads',        'Leads'
    OPPORTUNITIES = 'opportunities', 'Opportunities'
    AI_AGENTS   = 'ai_agents',    'AI Agents'
    CAMPAIGNS   = 'campaigns',    'Campaigns'
    PROPOSALS   = 'proposals',    'Proposal Builder'
    SETTINGS    = 'settings',     'Settings & User Management'


class Action(models.TextChoices):
    CREATE   = 'create',   'Create'
    READ     = 'read',     'Read'
    UPDATE   = 'update',   'Update'
    DELETE   = 'delete',   'Delete'
    OVERRIDE = 'override', 'Override (Cross-Record Edit)'
    EXPORT   = 'export',   'Export'
    IMPORT   = 'import',   'Import'
    PUBLISH  = 'publish',  'Publish / Approve'


class Scope(models.TextChoices):
    NONE = 'none', 'No Access'
    OWN  = 'own',  'Own Records Only'
    TEAM = 'team', 'Team Records'
    ALL  = 'all',  'Company-Wide'


# ─────────────────────────────────────────────────────────────────────────────
# Built-in Role Names (seed via data migration)
# ─────────────────────────────────────────────────────────────────────────────
ROLE_SUPER_ADMIN       = 'Super Admin'
ROLE_ADMIN             = 'Admin'
ROLE_SALES_MANAGER     = 'Sales Manager'
ROLE_SALES_REP         = 'Sales Rep'
ROLE_MARKETING_MANAGER = 'Marketing Manager'
ROLE_MARKETING_EXEC    = 'Marketing Executive'
ROLE_AI_AGENT_ADMIN    = 'AI Agent Admin'
ROLE_READ_ONLY         = 'Read-Only'


# ─────────────────────────────────────────────────────────────────────────────
# Team
# ─────────────────────────────────────────────────────────────────────────────
class Team(models.Model):
    """
    A logical team within an organization (e.g. 'Sales – North',
    'Marketing').  The manager field points to the Sales Manager user.
    """
    name         = models.CharField(max_length=150)
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='teams',
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_teams',
        help_text="Sales Manager responsible for this team.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label   = 'rbac_roles'
        unique_together = ('name', 'organization')
        ordering    = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


# ─────────────────────────────────────────────────────────────────────────────
# Role
# ─────────────────────────────────────────────────────────────────────────────
class Role(models.Model):
    """
    A named role (e.g. 'Sales Rep').  One user holds exactly one role.
    Permissions are attached via the Permission model.
    """
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_system   = models.BooleanField(
        default=True,
        help_text="System roles are pre-seeded and cannot be renamed/deleted.",
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'rbac_roles'
        ordering  = ['name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────────────────────
# Permission
# ─────────────────────────────────────────────────────────────────────────────
class Permission(models.Model):
    """
    Stores one row per (role, module, action) combination describing
    what scope that role has for that action on that module.
    """
    role   = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='permissions',
    )
    module = models.CharField(max_length=30, choices=Module.choices)
    action = models.CharField(max_length=30, choices=Action.choices)
    scope  = models.CharField(max_length=10, choices=Scope.choices, default=Scope.NONE)

    class Meta:
        app_label       = 'rbac_roles'
        unique_together  = ('role', 'module', 'action')
        ordering         = ['role', 'module', 'action']

    def __str__(self):
        return f"{self.role.name} | {self.module} | {self.action} → {self.scope}"


# ─────────────────────────────────────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────────────────────────────────────
class AuditLog(models.Model):
    """
    Immutable audit trail.  Created by signals/middleware.
    No update/delete is permitted (enforced by the manager below).
    """
    ACTION_TYPES = [
        ('login',          'Login'),
        ('logout',         'Logout'),
        ('login_failed',   'Login Failed'),
        ('create',         'Record Created'),
        ('update',         'Record Updated'),
        ('delete',         'Record Deleted'),
        ('export',         'Data Exported'),
        ('import',         'Data Imported'),
        ('role_change',    'Role Changed'),
        ('lead_reassign',  'Lead Reassigned'),
        ('camp_publish',   'Campaign Published'),
        ('camp_pause',     'Campaign Paused'),
        ('camp_delete',    'Campaign Deleted'),
        ('agent_activate', 'Agent Activated'),
        ('agent_config',   'Agent Configured'),
        ('agent_override', 'Agent Override'),
        ('access_denied',  'Access Denied (403)'),
    ]

    timestamp          = models.DateTimeField(default=timezone.now, editable=False)
    user               = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
    )
    user_role          = models.CharField(max_length=100, blank=True)
    action_type        = models.CharField(max_length=30, choices=ACTION_TYPES)
    module             = models.CharField(max_length=30, choices=Module.choices, blank=True)
    affected_record_id = models.CharField(max_length=100, blank=True)
    extra_data         = models.JSONField(
        default=dict, blank=True,
        help_text="Before/after values, counts, extra context."
    )
    ip_address         = models.GenericIPAddressField(null=True, blank=True)
    success            = models.BooleanField(default=True)

    class Meta:
        app_label = 'rbac_roles'
        ordering  = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        user_str = self.user.username if self.user else 'Anonymous'
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {user_str} – {self.action_type}"

    def save(self, *args, **kwargs):
        # Audit logs are append-only: never allow updates.
        if self.pk:
            raise ValueError("AuditLog records are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog records cannot be deleted.")
