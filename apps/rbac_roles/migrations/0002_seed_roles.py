"""
Seed migration: creates the 7 canonical roles and their permission matrix
as defined in CRM_RBAC_Specification.docx.

Run:  python manage.py migrate rbac_roles
"""
from django.db import migrations

# ─────────────────────────────────────────────────────────────────────────────
# Full permission matrix from the spec document.
# Format: (role_name, module, action, scope)
# ─────────────────────────────────────────────────────────────────────────────
ROLES = [
    ('Super Admin',          'Typically the CRM owner or IT administrator. Full system access.'),
    ('Sales Manager',        'Team lead. Oversees all leads and opportunities for their team.'),
    ('Sales Rep',            'Frontline salesperson. Full ownership of their own records only.'),
    ('Marketing Manager',    'Owns the full marketing function. Manages campaigns end-to-end.'),
    ('Marketing Executive',  'Junior marketing. Can create draft campaigns but not publish.'),
    ('AI Agent Admin',       'Technical / ops role. Configures and monitors AI agents.'),
    ('Read-Only',            'C-suite / auditor. View-only access across all modules.'),
]

PERMISSIONS = [
    # ── DASHBOARD ──
    # (role, module, action, scope)
    ('Super Admin',         'dashboard', 'read',   'all'),
    ('Sales Manager',       'dashboard', 'read',   'team'),
    ('Sales Rep',           'dashboard', 'read',   'own'),
    ('Marketing Manager',   'dashboard', 'read',   'team'),
    ('Marketing Executive', 'dashboard', 'read',   'own'),
    ('AI Agent Admin',      'dashboard', 'read',   'own'),
    ('Read-Only',           'dashboard', 'read',   'all'),

    # ── LEADS ──
    ('Super Admin',         'leads', 'read',     'all'),
    ('Super Admin',         'leads', 'create',   'all'),
    ('Super Admin',         'leads', 'update',   'all'),
    ('Super Admin',         'leads', 'delete',   'all'),
    ('Super Admin',         'leads', 'override', 'all'),
    ('Super Admin',         'leads', 'export',   'all'),
    ('Super Admin',         'leads', 'import',   'all'),

    ('Sales Manager',       'leads', 'read',     'team'),
    ('Sales Manager',       'leads', 'create',   'team'),
    ('Sales Manager',       'leads', 'update',   'team'),
    ('Sales Manager',       'leads', 'delete',   'team'),
    ('Sales Manager',       'leads', 'override', 'team'),
    ('Sales Manager',       'leads', 'export',   'team'),
    ('Sales Manager',       'leads', 'import',   'team'),

    ('Sales Rep',           'leads', 'read',     'own'),
    ('Sales Rep',           'leads', 'create',   'own'),
    ('Sales Rep',           'leads', 'update',   'own'),
    ('Sales Rep',           'leads', 'export',   'own'),

    ('Marketing Manager',   'leads', 'read',     'all'),
    ('Marketing Manager',   'leads', 'create',   'all'),
    ('Marketing Manager',   'leads', 'update',   'all'),
    ('Marketing Manager',   'leads', 'override', 'all'),
    ('Marketing Manager',   'leads', 'export',   'all'),
    ('Marketing Manager',   'leads', 'import',   'all'),

    ('Marketing Executive', 'leads', 'read',     'own'),
    ('Marketing Executive', 'leads', 'create',   'own'),
    ('Marketing Executive', 'leads', 'update',   'own'),

    ('AI Agent Admin',      'leads', 'read',     'all'),

    ('Read-Only',           'leads', 'read',     'all'),

    # ── OPPORTUNITIES ──
    ('Super Admin',         'opportunities', 'read',     'all'),
    ('Super Admin',         'opportunities', 'create',   'all'),
    ('Super Admin',         'opportunities', 'update',   'all'),
    ('Super Admin',         'opportunities', 'delete',   'all'),
    ('Super Admin',         'opportunities', 'override', 'all'),
    ('Super Admin',         'opportunities', 'export',   'all'),

    ('Sales Manager',       'opportunities', 'read',     'team'),
    ('Sales Manager',       'opportunities', 'update',   'team'),
    ('Sales Manager',       'opportunities', 'delete',   'team'),
    ('Sales Manager',       'opportunities', 'override', 'team'),
    ('Sales Manager',       'opportunities', 'export',   'team'),

    ('Sales Rep',           'opportunities', 'read',     'own'),
    ('Sales Rep',           'opportunities', 'create',   'own'),
    ('Sales Rep',           'opportunities', 'update',   'own'),
    ('Sales Rep',           'opportunities', 'export',   'own'),

    ('Read-Only',           'opportunities', 'read',     'all'),

    # ── AI AGENTS ──
    ('Super Admin',         'ai_agents', 'read',     'all'),
    ('Super Admin',         'ai_agents', 'create',   'all'),
    ('Super Admin',         'ai_agents', 'update',   'all'),
    ('Super Admin',         'ai_agents', 'delete',   'all'),
    ('Super Admin',         'ai_agents', 'override', 'all'),

    ('Sales Manager',       'ai_agents', 'read',     'all'),

    ('Marketing Manager',   'ai_agents', 'read',     'all'),
    ('Marketing Manager',   'ai_agents', 'override', 'all'),   # assign to campaign

    ('AI Agent Admin',      'ai_agents', 'read',     'all'),
    ('AI Agent Admin',      'ai_agents', 'create',   'all'),
    ('AI Agent Admin',      'ai_agents', 'update',   'all'),
    ('AI Agent Admin',      'ai_agents', 'override', 'all'),   # assign + stop

    ('Read-Only',           'ai_agents', 'read',     'all'),

    # ── CAMPAIGNS ──
    ('Super Admin',         'campaigns', 'read',     'all'),
    ('Super Admin',         'campaigns', 'create',   'all'),
    ('Super Admin',         'campaigns', 'update',   'all'),
    ('Super Admin',         'campaigns', 'delete',   'all'),
    ('Super Admin',         'campaigns', 'publish',  'all'),
    ('Super Admin',         'campaigns', 'export',   'all'),
    ('Super Admin',         'campaigns', 'override', 'all'),

    ('Sales Manager',       'campaigns', 'read',     'all'),

    ('Sales Rep',           'campaigns', 'read',     'all'),

    ('Marketing Manager',   'campaigns', 'read',     'all'),
    ('Marketing Manager',   'campaigns', 'create',   'all'),
    ('Marketing Manager',   'campaigns', 'update',   'all'),
    ('Marketing Manager',   'campaigns', 'delete',   'all'),
    ('Marketing Manager',   'campaigns', 'publish',  'all'),
    ('Marketing Manager',   'campaigns', 'export',   'all'),
    ('Marketing Manager',   'campaigns', 'override', 'all'),

    ('Marketing Executive', 'campaigns', 'read',     'all'),
    ('Marketing Executive', 'campaigns', 'create',   'own'),
    ('Marketing Executive', 'campaigns', 'update',   'own'),
    ('Marketing Executive', 'campaigns', 'override', 'own'),   # assign/remove leads

    ('AI Agent Admin',      'campaigns', 'read',     'all'),
    ('AI Agent Admin',      'campaigns', 'override', 'all'),   # link agent to campaign

    ('Read-Only',           'campaigns', 'read',     'all'),

    # ── SETTINGS ──
    ('Super Admin',         'settings',  'read',     'all'),
    ('Super Admin',         'settings',  'create',   'all'),
    ('Super Admin',         'settings',  'update',   'all'),
    ('Super Admin',         'settings',  'delete',   'all'),
]


def seed_roles_and_permissions(apps, schema_editor):
    Role       = apps.get_model('rbac_roles', 'Role')
    Permission = apps.get_model('rbac_roles', 'Permission')

    role_map = {}
    for name, desc in ROLES:
        role, _ = Role.objects.get_or_create(
            name=name,
            defaults={'description': desc, 'is_system': True},
        )
        role_map[name] = role

    for role_name, module, action, scope in PERMISSIONS:
        role = role_map[role_name]
        Permission.objects.get_or_create(
            role=role, module=module, action=action,
            defaults={'scope': scope},
        )


def unseed(apps, schema_editor):
    Role       = apps.get_model('rbac_roles', 'Role')
    Permission = apps.get_model('rbac_roles', 'Permission')
    Permission.objects.all().delete()
    Role.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rbac_roles', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_roles_and_permissions, reverse_code=unseed),
    ]
