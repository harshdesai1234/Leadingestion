"""
Custom allauth adapter.

On SIGNUP:
  - If a pending invite token is in the session → join that org (don't create new one).
  - Otherwise → auto-create a brand-new Organization for the user.

On LOGIN (post_login hook):
  - If a pending invite token is in the session → link user to that org.
"""
import logging

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

from .invite_views import SESSION_INVITE_KEY

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):

    # ── Signup Gate ───────────────────────────────────────────────────────────

    def is_open_for_signup(self, request):
        """
        Control whether the public /accounts/signup/ page is open.

        - If ALLOW_PUBLIC_SIGNUP=True (default) → anyone can sign up normally.
        - If ALLOW_PUBLIC_SIGNUP=False → only invite-link holders can register;
          direct visits to /signup/ get a 'closed' message.

        Invite links store a token in the session before redirecting to signup,
        so invited users are still allowed through even when signup is closed.
        """
        allow = getattr(settings, 'ALLOW_PUBLIC_SIGNUP', True)
        if allow:
            return True
        # Even when closed, let through users arriving via invite link
        has_invite = bool(request.session.get(SESSION_INVITE_KEY))
        return has_invite

    # ── Signup ────────────────────────────────────────────────────────────────

    def save_user(self, request, user, form, commit=True):
        """Auto-create or auto-join an org when a new user signs up."""
        user = super().save_user(request, user, form, commit=False)

        if commit:
            user.save()

            # Check for a pending invite first
            invite_token = request.session.get(SESSION_INVITE_KEY)
            if invite_token:
                self._join_org_via_invite(request, user, invite_token)
            else:
                self._create_new_org(request, user, form)

        return user

    def _join_org_via_invite(self, request, user, token_str):
        """On signup via invite link: join the existing org instead of creating a new one."""
        try:
            from .models import Invitation, UserProfile

            invite = Invitation.objects.select_related('organization').get(
                token=token_str,
                status=Invitation.STATUS_PENDING,
            )

            if not invite.is_valid():
                logger.warning(f"Invite {token_str} is expired/invalid during signup for {user.email}")
                # Fall back to creating a solo org
                self._create_new_org(request, user, None)
                return

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.organization = invite.organization
            profile.role = 'member'
            profile.org_name = invite.organization.name
            profile.org_id   = invite.organization.customer_id
            profile.save()

            invite.mark_accepted(user)

            # Clean up session
            request.session.pop(SESSION_INVITE_KEY, None)
            logger.info(f"User {user.email} joined org {invite.organization.customer_id} via invite")

        except Exception as exc:
            logger.error(f"Error joining org via invite for {user.email}: {exc}")
            self._create_new_org(request, user, None)

    def _create_new_org(self, request, user, form):
        """Create a brand-new Organization for a freshly signed-up user."""
        try:
            from .models import Organization, UserProfile

            company_name = ''
            if form and hasattr(form, 'cleaned_data'):
                company_name = form.cleaned_data.get('company_name', '')
            if not company_name:
                company_name = (
                    user.email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
                )

            org = Organization.objects.create(name=company_name, owner=user)

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.organization = org
            profile.role = 'owner'
            profile.org_name = org.name
            profile.org_id   = org.customer_id
            
            from rbac_roles.models import Role, ROLE_SUPER_ADMIN
            super_admin_role = Role.objects.filter(name=ROLE_SUPER_ADMIN).first()
            if super_admin_role:
                profile.rbac_role = super_admin_role

            profile.save()

        except Exception as exc:
            logger.error(f"Failed to create organization for {user.email}: {exc}")

    # ── Login (existing user) ─────────────────────────────────────────────────

    def pre_login(self, request, user, **kwargs):
        """
        Called by allauth just before logging in an existing user.
        If there's a pending invite token in the session, link the user to that org.
        """
        super().pre_login(request, user, **kwargs)

        invite_token = request.session.get(SESSION_INVITE_KEY)
        if invite_token:
            self._process_invite_on_login(request, user, invite_token)

    def _process_invite_on_login(self, request, user, token_str):
        """Link an existing user to the invited org after they log in."""
        try:
            from .models import Invitation
            from .invite_views import _link_user_to_org

            invite = Invitation.objects.select_related('organization').get(
                token=token_str,
                status=Invitation.STATUS_PENDING,
            )

            if invite.is_valid():
                _link_user_to_org(user, invite)
                request.session.pop(SESSION_INVITE_KEY, None)
                logger.info(f"Existing user {user.email} linked to org {invite.organization.customer_id} via invite")

        except Exception as exc:
            logger.error(f"Error processing invite on login for {user.email}: {exc}")
