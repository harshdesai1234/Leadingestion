"""
Admin Settings hub view — tab-based settings page for Admin / Super Admin.
Combines: Team Members (invite), Manage Teams, and Role Permissions.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from accounts.models import UserProfile, Organization
from rbac_roles.models import Role, Permission, Team, Module, Action, Scope, ROLE_SUPER_ADMIN, ROLE_ADMIN
from rbac_roles.utils import require_admin_role
from scheduling.models import OrgSmtpSetting, OrgCalendarCredential
from django.contrib import messages


SCOPE_LABELS = {
    Scope.ALL:  {'label': 'Full',  'color': '#10b981', 'icon': '✦'},
    Scope.TEAM: {'label': 'Team',  'color': '#f59e0b', 'icon': '◈'},
    Scope.OWN:  {'label': 'Own',   'color': '#3b82f6', 'icon': '●'},
    Scope.NONE: {'label': '—',     'color': '#d1d5db', 'icon': '—'},
}

MODULES = [
    ('dashboard',     'Dashboard'),
    ('leads',         'Leads'),
    ('opportunities', 'Opportunities'),
    ('campaigns',     'Campaigns'),
    ('ai_agents',     'AI Agents'),
    ('settings',      'Settings'),
]

ACTIONS = ['read', 'create', 'update', 'delete', 'export', 'publish']

CREDIT_PACKAGES = [
    {'credits': 1000, 'price': 10},
    {'credits': 2500, 'price': 25},
    {'credits': 5000, 'price': 50},
    {'credits': 10000, 'price': 100},
    {'credits': 20000, 'price': 200},
]


@login_required
@require_admin_role
def admin_settings(request):
    """
    Settings hub — tabbed page combining Invite Members, Teams, and Role Permissions.
    """
    tab = request.GET.get('tab', 'members')
    if tab not in ('members', 'teams', 'roles', 'billing', 'email'):
        tab = 'members'

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    org = profile.organization

    # ── Members tab data ──────────────────────────────────────────────────────
    from accounts.models import Invitation
    members = UserProfile.objects.filter(organization=org).select_related('user', 'rbac_role') if org else []
    invitations = Invitation.objects.filter(organization=org).order_by('-created_at') if org else []
    roles = Role.objects.all().order_by('name')
    is_console_email = _is_console_email()

    # ── Teams tab data ────────────────────────────────────────────────────────
    teams = Team.objects.filter(organization=org).prefetch_related('members') if org else []

    # ── Roles tab data ────────────────────────────────────────────────────────
    all_roles = list(Role.objects.all().order_by('name').prefetch_related('permissions'))
    perm_map = {}
    for role in all_roles:
        perm_map[role.id] = {}
        for mod_key, _ in MODULES:
            perm_map[role.id][mod_key] = {}
            for action in ACTIONS:
                perm_map[role.id][mod_key][action] = SCOPE_LABELS[Scope.NONE]

        for perm in role.permissions.all():
            if perm.module in perm_map[role.id] and perm.action in ACTIONS:
                perm_map[role.id][perm.module][perm.action] = SCOPE_LABELS.get(perm.scope, SCOPE_LABELS[Scope.NONE])

    # ── Billing tab data ──────────────────────────────────────────────────────
    from accounts.credit_service import get_credit_account
    credit_account = get_credit_account(org) if org else None
    category_usage = []
    
    if credit_account:
        # Process per-category usage
        usage_data = credit_account.feature_usage or {}
        limit_data = (credit_account.plan.feature_limits or {}) if credit_account.plan else {}
        
        feature_names = {
            'ai_bdr_per_minute': 'AI BDR',
            'ai_receptionist_per_minute': 'AI Receptionist',
            'lead_enrichment_email': 'Email Enrichment',
            'lead_enrichment_phone': 'Phone Enrichment',
            'email_generation': 'Email Generation',
            'slide_per_slide': 'Slide Builder',
            'note_taker_per_30min': 'Note Taker',
        }
        
        for key, name in feature_names.items():
            used = usage_data.get(key, 0)
            limit = limit_data.get(key)
            
            percentage = 0
            if limit and limit > 0:
                percentage = min(100, int((used / limit) * 100))
            
            category_usage.append({
                'key': key,
                'name': name,
                'used': used,
                'limit': limit,
                'percentage': percentage,
                'is_limited': limit is not None and limit > 0
            })

    # ── Billing history ───────────────────────────────────────────────────────
    billing_payments = []
    if org:
        from payment.models import Payment
        org_user_ids = org.members.values_list('user_id', flat=True)
        billing_payments = Payment.objects.filter(
            user_id__in=org_user_ids,
            payment_status='completed'
        ).order_by('-created_at')[:10]

    # ── Email & Calendar tab data ─────────────────────────────────────────────
    smtp_setting = None
    google_cred = None
    outlook_cred = None
    if org:
        smtp_setting = OrgSmtpSetting.objects.filter(organization=org).first()
        google_cred = OrgCalendarCredential.objects.filter(organization=org, provider='google').first()
        outlook_cred = OrgCalendarCredential.objects.filter(organization=org, provider='outlook').first()

    if request.method == 'POST':
        section = request.POST.get('section')

        if section == 'smtp':
            host = request.POST.get('host', '').strip()
            port = int(request.POST.get('port', 587))
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '').strip()
            use_tls = request.POST.get('use_tls') == 'on'
            use_ssl = request.POST.get('use_ssl') == 'on'
            from_name = request.POST.get('from_name', '').strip()

            if smtp_setting:
                smtp_setting.host = host
                smtp_setting.port = port
                smtp_setting.username = username
                if password:
                    smtp_setting.password = password
                smtp_setting.use_tls = use_tls
                smtp_setting.use_ssl = use_ssl
                smtp_setting.from_name = from_name
                smtp_setting.save()
            else:
                smtp_setting = OrgSmtpSetting.objects.create(
                    organization=org, host=host, port=port, username=username,
                    password=password, use_tls=use_tls, use_ssl=use_ssl, from_name=from_name,
                )
            messages.success(request, "SMTP settings saved.")

        elif section == 'google_creds':
            client_id = request.POST.get('client_id', '').strip()
            client_secret = request.POST.get('client_secret', '').strip()
            if google_cred:
                google_cred.client_id = client_id
                google_cred.client_secret = client_secret
                google_cred.save(update_fields=['client_id', 'client_secret', 'updated_at'])
            else:
                google_cred = OrgCalendarCredential.objects.create(
                    organization=org, provider='google', client_id=client_id, client_secret=client_secret,
                )
            messages.success(request, "Google credentials saved. Click 'Connect Google Calendar' to authorize.")

        elif section == 'outlook_creds':
            client_id = request.POST.get('client_id', '').strip()
            client_secret = request.POST.get('client_secret', '').strip()
            if outlook_cred:
                outlook_cred.client_id = client_id
                outlook_cred.client_secret = client_secret
                outlook_cred.save(update_fields=['client_id', 'client_secret', 'updated_at'])
            else:
                outlook_cred = OrgCalendarCredential.objects.create(
                    organization=org, provider='outlook', client_id=client_id, client_secret=client_secret,
                )
            messages.success(request, "Outlook credentials saved. Click 'Connect Outlook' to authorize.")

        # Redirect to the same tab after POST
        from django.shortcuts import redirect
        from django.urls import reverse
        return redirect(reverse('admin_settings') + '?tab=email')

    google_redirect_uri = request.build_absolute_uri('/scheduling/oauth/google/callback/')
    outlook_redirect_uri = request.build_absolute_uri('/scheduling/oauth/outlook/callback/')

    return render(request, 'settings/admin_settings.html', {
        'active_tab': tab,
        # Members
        'members': members,
        'invitations': invitations,
        'roles': roles,
        'org': org,
        'is_console_email': is_console_email,
        'now': timezone.now(),
        # Teams
        'teams': teams,
        # Roles
        'all_roles': all_roles,
        'modules': MODULES,
        'actions': ACTIONS,
        'perm_map': perm_map,
        # Billing
        'credit_account': credit_account,
        'category_usage': category_usage,
        'credit_packages': CREDIT_PACKAGES,
        'billing_payments': billing_payments,
        # Email & Calendar
        'smtp_setting': smtp_setting,
        'google_cred': google_cred,
        'outlook_cred': outlook_cred,
        'google_redirect_uri': google_redirect_uri,
        'outlook_redirect_uri': outlook_redirect_uri,
    })


def _is_console_email():
    try:
        from django.conf import settings
        backend = settings.EMAIL_BACKEND
        return 'console' in backend.lower() or 'locmem' in backend.lower()
    except Exception:
        return False


