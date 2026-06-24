"""
Invite-user views.

Flow:
  1. POST /accounts/invite/send/      → owner sends invite email
  2. GET  /accounts/invite/accept/<token>/  → invitee clicks link in email

  New user path:
    token saved in session → redirected to /accounts/signup/
    adapter reads session token on signup → joins existing org (no new org created)

  Existing user path:
    if logged in → org linked immediately
    if not logged in → token in session → redirect to login
    signal on login picks up the pending token and links org
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .models import Invitation, Organization, UserProfile
from rbac_roles.models import Role, ROLE_SALES_REP
from rbac_roles.utils import require_admin_role

logger = logging.getLogger(__name__)

SESSION_INVITE_KEY = 'pending_invite_token'

print(">>> invite_views.py LOADED — resend/delete views active <<<", flush=True)


# ─── Send Invite ──────────────────────────────────────────────────────────────

@login_required
@require_admin_role
def invite_users_page(request):
    """
    GET  → show the invite form + list of existing invites for this org.
    POST → send a new invite.
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    org = profile.organization

    if not org:
        messages.error(request, "You must belong to an organization to invite users.")
        return redirect('dashboard:home')

    if request.method == 'POST':
        return _handle_send_invite(request, org)

    # GET — show page
    invitations = Invitation.objects.filter(organization=org).select_related('invited_by', 'accepted_by')
    members     = org.members.select_related('user').all()

    # Diagnostic: detect console backend so we can warn the user in the UI
    email_backend   = getattr(settings, 'EMAIL_BACKEND', '')
    is_console_email = 'console' in email_backend.lower()
    email_host      = getattr(settings, 'EMAIL_HOST', '')
    email_from      = getattr(settings, 'DEFAULT_FROM_EMAIL', '')

    return render(request, 'account/invite_users.html', {
        'org': org,
        'invitations': invitations,
        'members': members,
        'roles': Role.objects.all().order_by('name'),
        'now': timezone.now(),
        'is_console_email': is_console_email,
        'email_host': email_host,
        'email_from': email_from,
    })


def _handle_send_invite(request, org):
    """Process the invite form submission."""
    email = request.POST.get('email', '').strip().lower()
    role_id = request.POST.get('role_id', '').strip()
    print(f"[INVITE] _handle_send_invite called | email={email!r} | org={org} | role_id={role_id!r}")
    if not email:
        messages.error(request, "Please enter an email address.")
        return redirect('invite_users')

    # Don't invite someone already in this org or in another org
    existing_user = User.objects.filter(email__iexact=email).first()
    if existing_user:
        try:
            profile = existing_user.profile
            if profile.organization:
                if profile.organization == org:
                    messages.warning(request, f"User {email} is already a member of your organization.")
                else:
                    messages.error(
                        request, 
                        f"User with email {email} is already registered in another organization. "
                        "To prevent data conflicts, you cannot invite them to your organization."
                    )
                return redirect('invite_users')
        except Exception:
            # If no profile or org, we can proceed (e.g. if they were partially deleted or skipped org setup)
            pass

    # Don't send a duplicate pending invite
    existing = Invitation.objects.filter(
        organization=org, email__iexact=email, status=Invitation.STATUS_PENDING
    ).first()
    print(f"[INVITE] duplicate check | existing={existing} | valid={existing.is_valid() if existing else 'n/a'}")
    if existing and existing.is_valid():
        messages.warning(request, f"A pending invite for {email} already exists.")
        print(f"[INVITE] BLOCKED by duplicate check — use Resend button instead")
        return redirect('invite_users')

    # Create the invite
    rbac_role = None
    if role_id and role_id.isdigit():
        try:
            rbac_role = Role.objects.get(pk=int(role_id))
        except Role.DoesNotExist:
            pass
    invite = Invitation.objects.create(
        organization=org,
        invited_by=request.user,
        email=email,
        rbac_role=rbac_role,
    )

    # Send the email — show a graceful error if it fails (invite is still saved)
    try:
        _send_invite_email(invite, request)
        messages.success(request, f"Invite sent to {email}!")
    except Exception as exc:
        logger.error(f"Failed to send invite email to {email}: {exc}")
        messages.warning(
            request,
            f"Invite created for {email} but the email could not be delivered. "
            f"Use the Resend button to try again."
        )

    return redirect('invite_users')


def _send_invite_email(invite: Invitation, request):
    """Render and send the invite email."""
    # Log the active email backend so it's easy to debug delivery issues
    backend = getattr(settings, 'EMAIL_BACKEND', 'unknown')
    host    = getattr(settings, 'EMAIL_HOST', '')
    port    = getattr(settings, 'EMAIL_PORT', '')
    use_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
    use_tls = getattr(settings, 'EMAIL_USE_TLS', False)
    logger.info(
        f"[email] Sending invite to {invite.email} | "
        f"backend={backend} host={host}:{port} SSL={use_ssl} TLS={use_tls}"
    )

    # Build the accept URL from the actual request host so it works on AWS
    # (avoids the localhost:8000 fallback that SITE_BASE_URL can produce)
    accept_path = reverse('accept_invite', kwargs={'token': str(invite.token)})
    accept_url  = request.build_absolute_uri(accept_path)

    subject = f"You're invited to join {invite.organization.name} on Agentyne"

    context = {
        'invite': invite,
        'inviter_name': invite.invited_by.get_full_name() or invite.invited_by.email,
        'org_name': invite.organization.name,
        'accept_url': accept_url,
        'customer_id': invite.organization.customer_id,
    }

    try:
        html_message  = render_to_string('email/invite_email.html', context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invite.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Invite email sent to {invite.email} for org {invite.organization.customer_id}")
    except Exception as exc:
        logger.error(f"Failed to send invite email to {invite.email}: {exc}")
        raise  # re-raise so callers can show a user-friendly message


# ─── Accept Invite ────────────────────────────────────────────────────────────

def accept_invite(request, token):
    """
    Invitee lands here after clicking the email link.
    Handles three cases:
      A) Already logged in → link org immediately
      B) Not logged in, existing account → store token, redirect to login
      C) Not logged in, no account → store token, redirect to signup
      
    GET request: Renders a preview page confirming they want to join.
    POST request: Actually processes the invite.
    """
    try:
        invite = Invitation.objects.get(token=token)
    except Invitation.DoesNotExist:
        return render(request, 'account/invite_invalid.html', {
            'reason': 'not_found',
            'org_name': '',
        })

    if not invite.is_valid():
        return render(request, 'account/invite_invalid.html', {
            'reason': 'expired' if invite.status == Invitation.STATUS_PENDING else 'already_used',
            'org_name': invite.organization.name,
        })
        
    if request.method == 'GET':
        return render(request, 'account/invite_confirm.html', {
            'invite': invite,
            'org_name': invite.organization.name,
            'inviter_name': invite.invited_by.get_full_name() or invite.invited_by.email,
        })

    # ── Handle POST Request ───────────────
    # ── Case A: Already logged in ─────────
    if request.user.is_authenticated:
        # If the logged-in user's email matches the invite (or we allow any)
        _link_user_to_org(request.user, invite)
        messages.success(
            request,
            f"You've joined {invite.organization.name}! "
            f"Your workspace is now shared with your team."
        )
        return redirect('dashboard:home')

    # ── Store token in session for post-auth pickup ──────
    request.session[SESSION_INVITE_KEY] = str(token)
    request.session.modified = True

    # ── Case B/C: decide signup vs login ────────────────
    email = invite.email
    user_exists = User.objects.filter(email__iexact=email).exists()

    if user_exists:
        # Existing user → send to login; signal will finish the job
        messages.info(
            request,
            f"You have an existing account. Please log in to join {invite.organization.name}."
        )
        return redirect(f"/accounts/login/?next=/accounts/invite/accept/{token}/")
    else:
        # New user → pre-create an inactive account, link to invite org, and
        # send a password-set link. This matches the admin-created user flow so
        # the invitee is prompted to choose a password before their first login.
        # Org is linked immediately (no session dependency).
        new_user = _create_inactive_invited_user(email, invite)
        uid   = urlsafe_base64_encode(force_bytes(new_user.pk))
        pw_token = default_token_generator.make_token(new_user)
        set_pw_url = request.build_absolute_uri(
            f"/accounts/reset/{uid}/{pw_token}/"
        )
        messages.info(
            request,
            f"A password-setup link has been sent to {email}. "
            f"Please check your inbox to complete signup and join {invite.organization.name}."
        )
        logger.info(f"[INVITE] Pre-created inactive user {email}, sending password-set email.")
        try:
            _send_invite_set_password_email(new_user, invite, set_pw_url)
        except Exception as exc:
            logger.error(f"[INVITE] Failed to send password-set email to {email}: {exc}")
        return redirect("/accounts/login/")



# ─── Resend Invite ────────────────────────────────────────────────────────────

@login_required
@require_admin_role
def resend_invite(request, token):
    """Re-send an invite email and reset its 7-day expiry window."""
    if request.method != 'POST':
        return redirect('invite_users')

    invite = get_object_or_404(Invitation, token=token)

    # Security: only members of the same org can resend
    try:
        profile = request.user.profile
    except Exception:
        profile = None

    if not profile or profile.organization_id != invite.organization_id:
        messages.error(request, "You don't have permission to resend this invite.")
        return redirect('invite_users')

    if invite.status == Invitation.STATUS_ACCEPTED:
        messages.warning(request, f"{invite.email} has already accepted the invite.")
        return redirect('invite_users')

    # Reset expiry and status, then resend
    invite.expires_at = timezone.now() + timedelta(days=7)
    invite.status = Invitation.STATUS_PENDING
    invite.save()
    print(f"[RESEND] Attempting resend | email={invite.email} | org={invite.organization} | backend={getattr(settings, 'EMAIL_BACKEND', '?')}")

    try:
        _send_invite_email(invite, request)
        print(f"[RESEND] SUCCESS — email dispatched to {invite.email}")
        messages.success(request, f"Invite resent to {invite.email}.")
    except Exception as exc:
        print(f"[RESEND] FAILED — {type(exc).__name__}: {exc}")
        logger.error(f"Failed to resend invite to {invite.email}: {exc}")
        messages.error(request, f"Could not resend the email to {invite.email}. Please try again.")

    return redirect('invite_users')


# ─── Delete Invite ─────────────────────────────────────────────────────────────

@login_required
@require_admin_role
def delete_invite(request, token):
    """Delete a pending or expired invitation."""
    if request.method != 'POST':
        return redirect('invite_users')

    invite = get_object_or_404(Invitation, token=token)

    # Security: only members of the same org can delete
    try:
        profile = request.user.profile
    except Exception:
        profile = None

    if not profile or profile.organization_id != invite.organization_id:
        messages.error(request, "You don't have permission to delete this invite.")
        return redirect('invite_users')

    email = invite.email
    was_accepted = invite.status == Invitation.STATUS_ACCEPTED

    # If the invite was already accepted, delete the user entirely.
    # This removes them from the organization AND the system, allowing for a clean re-invite.
    # Their work (leads, tasks, etc.) is preserved via on_delete=SET_NULL.
    if was_accepted and invite.accepted_by:
        try:
            user_to_delete = invite.accepted_by
            user_to_delete.delete()  # This cascades to UserProfile
            logger.info(f"[DELETE INVITE] Hard deleted user {email} when invite was deleted.")
        except Exception as exc:
            logger.error(f"[DELETE INVITE] Failed to delete user {email}: {exc}")

    invite.delete()
    messages.success(request, f"Invitation for {email} has been deleted and the user has been removed from the organisation.")
    return redirect('invite_users')


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _link_user_to_org(user: User, invite: Invitation):
    """Link a user to the invite's organization, assign RBAC role, and mark the invite accepted."""
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # Only change org if they don't already belong to this one
    if profile.organization_id != invite.organization_id:
        profile.organization = invite.organization
        profile.role = 'member'
        profile.org_name = invite.organization.name
        profile.org_id   = invite.organization.customer_id

        # Assign RBAC role from invite; default to Sales Rep
        rbac_role = invite.rbac_role
        if rbac_role is None:
            rbac_role = Role.objects.filter(name=ROLE_SALES_REP).first()
        profile.rbac_role = rbac_role
        profile.save()

    invite.mark_accepted(user)


def _create_inactive_invited_user(email: str, invite: Invitation) -> User:
    """
    Pre-create a Django User for a new invitee.
    The account is inactive (is_active=False) with no usable password.
    It will be activated by CustomPasswordResetConfirmView when the user
    sets their password via the emailed link.

    The user is immediately linked to the invite org so that no session
    token is required at password-set time.
    """
    user = User.objects.create(
        username=email,
        email=email,
        is_active=False,
    )
    user.set_unusable_password()
    user.save()

    # Link to org right away, assign RBAC role from invite
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.organization = invite.organization
    profile.role         = 'member'
    profile.org_name     = invite.organization.name
    profile.org_id       = invite.organization.customer_id

    rbac_role = invite.rbac_role
    if rbac_role is None:
        rbac_role = Role.objects.filter(name=ROLE_SALES_REP).first()
    profile.rbac_role = rbac_role
    profile.save()

    invite.mark_accepted(user)
    return user


def _send_invite_set_password_email(user: User, invite: Invitation, set_pw_url: str):
    """Email the new invitee their password-setup link."""
    context = {
        'user': user,
        'invite': invite,
        'org_name': invite.organization.name,
        'inviter_name': invite.invited_by.get_full_name() or invite.invited_by.email,
        'set_pw_url': set_pw_url,
        'customer_id': invite.organization.customer_id,
    }
    html_message  = render_to_string('email/invite_set_password.html', context)
    plain_message = strip_tags(html_message)
    send_mail(
        subject=f"You're invited to join {invite.organization.name} on Agentyne — set your password",
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
    logger.info(f"[INVITE] Password-set email sent to {user.email}")
