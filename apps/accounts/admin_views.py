"""
Admin-controlled user creation.

Superadmins create users here instead of via the public signup page.
The new user gets an email with a "Set your password" link that uses
the existing CustomPasswordResetConfirmView (password_reset_confirm URL).

Flow:
  1. Superadmin fills form: email, first name, last name, company name.
  2. User is created with  is_active=False  and no usable password.
  3. An Organization is auto-created with a unique AGT-XXXXXXXX customer_id.
  4. A password-reset token is generated and emailed to the user.
  5. User clicks link → sets password → is_active=True → redirected to login.
  6. On next login, org is already set — no questions asked.
"""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode

from .models import Organization, UserProfile

logger = logging.getLogger(__name__)


# ─── Form (plain dict validation — no Django Form class needed) ───────────────

def _validate_form(post):
    """Return (cleaned_data, errors)."""
    data = {
        'email':        post.get('email', '').strip().lower(),
        'first_name':   post.get('first_name', '').strip(),
        'last_name':    post.get('last_name', '').strip(),
        'company_name': post.get('company_name', '').strip(),
    }
    errors = []
    if not data['email']:
        errors.append("Email is required.")
    elif User.objects.filter(email__iexact=data['email']).exists():
        errors.append(f"A user with email '{data['email']}' already exists.")
    if not data['company_name']:
        errors.append("Company name is required.")
    return data, errors


# ─── View ─────────────────────────────────────────────────────────────────────

@staff_member_required
def create_managed_user(request):
    """
    GET  → show the creation form.
    POST → create user + org + send onboarding email.
    """
    if request.method == 'POST':
        data, errors = _validate_form(request.POST)

        if errors:
            for err in errors:
                messages.error(request, err)
            recent_users = (
                User.objects.filter(is_superuser=False)
                .select_related('profile__organization')
                .order_by('-date_joined')[:20]
            )
            return render(request, 'admin/accounts/create_managed_user.html', {
                'form_data': data,
                'title': 'Create Managed User',
                'recent_users': recent_users,
            })

        try:
            user, org = _create_user_and_org(data)
            _send_onboarding_email(user, org, request)
            messages.success(
                request,
                f"User '{user.email}' created for org '{org.name}' ({org.customer_id}). "
                f"Onboarding email sent."
            )
            return redirect('admin:create_managed_user')   # stay on same page, show success

        except Exception as exc:
            logger.exception(f"Failed to create managed user: {exc}")
            messages.error(request, f"Error: {exc}")

    # GET  → show the creation form (optionally pre-filled via search params)
    initial_data = {
        'email':        request.GET.get('email', ''),
        'first_name':   request.GET.get('first_name', ''),
        'last_name':    request.GET.get('last_name', ''),
        'company_name': request.GET.get('org_name', ''),
    }

    # Show most-recent 20 managed users (non-superusers, ordered by newest)
    recent_users = (
        User.objects
        .filter(is_superuser=False)
        .select_related('profile__organization')
        .order_by('-date_joined')[:20]
    )
    return render(request, 'admin/accounts/create_managed_user.html', {
        'form_data': initial_data,
        'title': 'Create Managed User',
        'recent_users': recent_users,
    })


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _create_user_and_org(data: dict):
    """Create the Django user + org + user profile. Returns (user, org)."""

    # Create user — inactive until they set their password
    user = User.objects.create(
        username=data['email'],   # username = email (allauth style)
        email=data['email'],
        first_name=data['first_name'],
        last_name=data['last_name'],
        is_active=False,          # activated by CustomPasswordResetConfirmView
    )
    user.set_unusable_password()
    user.save()

    # Create organization
    org = Organization.objects.create(
        name=data['company_name'],
        owner=user,
    )

    # Link user profile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.organization  = org
    profile.role          = 'owner'
    profile.email_verified = False   # will be set after they set password
    profile.org_name      = org.name
    profile.org_id        = org.customer_id
    
    from rbac_roles.models import Role, ROLE_SUPER_ADMIN
    super_admin_role = Role.objects.filter(name=ROLE_SUPER_ADMIN).first()
    if super_admin_role:
        profile.rbac_role = super_admin_role
        
    profile.save()

    logger.info(f"Admin created user {user.email} in org {org.customer_id}")
    return user, org


def _send_onboarding_email(user: User, org: Organization, request):
    """Generate a password-set token and email it to the new user."""

    # Reuse Django's password reset token — validated by CustomPasswordResetConfirmView
    uid   = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    base_url    = getattr(settings, 'SITE_BASE_URL', 'http://localhost:8000')
    set_pw_url  = f"{base_url}/accounts/reset/{uid}/{token}/"

    subject = f"Your Agentyne account is ready — set your password"

    context = {
        'user':        user,
        'org':         org,
        'set_pw_url':  set_pw_url,
        'customer_id': org.customer_id,
        'inviter_name': request.user.get_full_name() or request.user.email,
    }

    html_message  = render_to_string('email/admin_user_onboarding.html', context)
    plain_message = strip_tags(html_message)

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
    logger.info(f"Onboarding email sent to {user.email}")
