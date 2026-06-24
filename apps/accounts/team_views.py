"""
Team management views — only Super Admin and Admin can manage teams.
Teams are org-scoped. Members are assigned via UserProfile.teams (M2M).
A user can belong to multiple teams simultaneously.
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages

from accounts.models import UserProfile, Organization
from rbac_roles.models import Team
from rbac_roles.utils import require_admin_role, log_audit

logger = logging.getLogger(__name__)
User = get_user_model()


@login_required
@require_admin_role
def team_list(request):
    """List all teams for the admin's organisation."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    org = profile.organization
    if not org:
        messages.error(request, "You must belong to an organisation to manage teams.")
        return redirect('dashboard:home')

    teams = Team.objects.filter(organization=org).prefetch_related('members')
    return render(request, 'rbac_roles/team_list.html', {
        'teams': teams,
        'org': org,
    })


@login_required
@require_admin_role
def team_create(request):
    """Create a new team for the current organisation."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    org = profile.organization
    if not org:
        messages.error(request, "You must belong to an organisation.")
        return redirect('dashboard:home')

    org_user_ids = list(UserProfile.objects.filter(organization=org).values_list('user_id', flat=True))
    org_members = UserProfile.objects.filter(organization=org).select_related('user', 'rbac_role')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        manager_id = request.POST.get('manager_id', '').strip()
        member_ids = request.POST.getlist('member_ids')

        if not name:
            messages.error(request, "Team name is required.")
        elif Team.objects.filter(organization=org, name=name).exists():
            messages.error(request, f"A team named '{name}' already exists.")
        else:
            manager = User.objects.filter(pk=manager_id, pk__in=org_user_ids).first() if manager_id else None
            team = Team.objects.create(organization=org, name=name, manager=manager)

            # Add selected members to the new team (M2M — does NOT remove from other teams)
            member_ids_int = [int(m) for m in member_ids if m.isdigit()]
            for profile_obj in UserProfile.objects.filter(organization=org, user_id__in=member_ids_int):
                profile_obj.teams.add(team)

            log_audit(request, 'create', module='settings',
                      affected_record_id=team.pk,
                      extra={'team_name': name, 'member_count': len(member_ids_int)})
            messages.success(request, f"Team '{name}' created with {len(member_ids_int)} member(s).")
            return redirect('team_list')

    return render(request, 'rbac_roles/team_form.html', {
        'org': org,
        'org_members': org_members,
        'mode': 'create',
    })


@login_required
@require_admin_role
def team_edit(request, pk):
    """Edit team name, manager, and membership."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    org = profile.organization
    team = get_object_or_404(Team, pk=pk, organization=org)

    org_user_ids = list(UserProfile.objects.filter(organization=org).values_list('user_id', flat=True))
    org_members = UserProfile.objects.filter(organization=org).select_related('user', 'rbac_role').prefetch_related('teams')
    # Current member user IDs for this team
    current_member_ids = list(
        UserProfile.objects.filter(organization=org, teams=team).values_list('user_id', flat=True)
    )

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        manager_id = request.POST.get('manager_id', '').strip()
        member_ids = request.POST.getlist('member_ids')

        if not name:
            messages.error(request, "Team name is required.")
        elif Team.objects.filter(organization=org, name=name).exclude(pk=pk).exists():
            messages.error(request, f"A team named '{name}' already exists.")
        else:
            team.name = name
            team.manager = User.objects.filter(pk=manager_id, pk__in=org_user_ids).first() if manager_id else None
            team.save()

            # Recompute membership: remove everyone currently in team, then add selected
            member_ids_int = [int(m) for m in member_ids if m.isdigit()]
            # Remove all current members from this team
            for profile_obj in UserProfile.objects.filter(organization=org, teams=team):
                profile_obj.teams.remove(team)
            # Add newly selected members (they keep any other team memberships)
            for profile_obj in UserProfile.objects.filter(organization=org, user_id__in=member_ids_int):
                profile_obj.teams.add(team)

            log_audit(request, 'update', module='settings',
                      affected_record_id=team.pk,
                      extra={'team_name': name, 'member_count': len(member_ids_int)})
            messages.success(request, f"Team '{name}' updated.")
            return redirect('team_list')

    return render(request, 'rbac_roles/team_form.html', {
        'org': org,
        'org_members': org_members,
        'team': team,
        'current_member_ids': current_member_ids,
        'mode': 'edit',
    })


@login_required
@require_admin_role
def team_delete(request, pk):
    """Delete a team (unassigns all members from it first)."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    org = profile.organization
    team = get_object_or_404(Team, pk=pk, organization=org)

    if request.method == 'POST':
        name = team.name
        # M2M: Django removes join-table rows automatically on delete
        log_audit(request, 'delete', module='settings', affected_record_id=pk,
                  extra={'team_name': name})
        team.delete()
        messages.success(request, f"Team '{name}' deleted. Members have been unassigned.")
        return redirect('team_list')

    members = UserProfile.objects.filter(teams=team).select_related('user')
    return render(request, 'rbac_roles/team_confirm_delete.html', {
        'team': team,
        'members': members,
    })
