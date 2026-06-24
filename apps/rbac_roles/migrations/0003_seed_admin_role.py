"""
Migration 0003: Seed 'Admin' role (same as Super Admin minus Settings module).
Also ensures all roles can read/create/edit pitches (campaigns module covers pitches).
"""
from django.db import migrations

ADMIN_ROLE = ('Admin', 'Same as Super Admin but cannot manage Settings or invite users.')

# Admin has full access to all modules EXCEPT settings
ADMIN_PERMISSIONS = [
    # Dashboard
    ('Admin', 'dashboard', 'read',   'all'),
    # Leads
    ('Admin', 'leads',     'read',   'all'),
    ('Admin', 'leads',     'create', 'all'),
    ('Admin', 'leads',     'update', 'all'),
    ('Admin', 'leads',     'delete', 'all'),
    ('Admin', 'leads',     'export', 'all'),
    ('Admin', 'leads',     'import', 'all'),
    ('Admin', 'leads',     'override','all'),
    # Opportunities
    ('Admin', 'opportunities', 'read',    'all'),
    ('Admin', 'opportunities', 'create',  'all'),
    ('Admin', 'opportunities', 'update',  'all'),
    ('Admin', 'opportunities', 'delete',  'all'),
    ('Admin', 'opportunities', 'override','all'),
    # Campaigns
    ('Admin', 'campaigns', 'read',    'all'),
    ('Admin', 'campaigns', 'create',  'all'),
    ('Admin', 'campaigns', 'update',  'all'),
    ('Admin', 'campaigns', 'delete',  'all'),
    ('Admin', 'campaigns', 'publish', 'all'),
    # AI Agents
    ('Admin', 'ai_agents', 'read',    'all'),
    ('Admin', 'ai_agents', 'create',  'all'),
    ('Admin', 'ai_agents', 'update',  'all'),
    ('Admin', 'ai_agents', 'delete',  'all'),
    # Settings — NO access (intentionally omitted)
]


def seed_admin_role(apps, schema_editor):
    Role       = apps.get_model('rbac_roles', 'Role')
    Permission = apps.get_model('rbac_roles', 'Permission')

    role, _ = Role.objects.get_or_create(
        name=ADMIN_ROLE[0],
        defaults={'description': ADMIN_ROLE[1], 'is_system': True},
    )

    for role_name, module, action, scope in ADMIN_PERMISSIONS:
        Permission.objects.get_or_create(
            role=role,
            module=module,
            action=action,
            defaults={'scope': scope},
        )


def remove_admin_role(apps, schema_editor):
    Role = apps.get_model('rbac_roles', 'Role')
    Role.objects.filter(name='Admin').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rbac_roles', '0002_seed_roles'),
    ]

    operations = [
        migrations.RunPython(seed_admin_role, remove_admin_role),
    ]
