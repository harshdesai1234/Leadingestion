import sys
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from dashboard.models import (
    CallRecord, BdrCampaign, BdrCampaignLead, BdrPitch, 
    UserAgent, AgentVoice, PromptTemplate, EmailConfiguration,
    SMTPServerSetting, OrganizationAgentConfig
)
from ai_receptionist.models import InboundCallRecord, AIReceptionist, FollowUp
from crm.models.lead import Lead, LeadNote
from rbac_roles.models import Team

class Command(BaseCommand):
    help = 'Safely delete an Organization or User and all associated orphaned data.'

    def add_arguments(self, parser):
        parser.add_argument('--org', type=str, help='Name or Customer ID of the organization to delete')
        parser.add_argument('--user', type=str, nargs='+', help='Email(s) or Username(s) of the user(s) to delete')
        parser.add_argument('--force', action='store_true', help='Skip confirmation and force deletion')

    def handle(self, *args, **options):
        org_identifier = options.get('org')
        user_identifiers = options.get('user')
        force = options.get('force')

        if not org_identifier and not user_identifiers:
            raise CommandError('You must provide either --org or --user')

        if org_identifier:
            self.delete_organization(org_identifier, force)
        elif user_identifiers:
            for identifier in user_identifiers:
                self.delete_user(identifier, force)

    def delete_organization(self, identifier, force):
        try:
            org = Organization.objects.filter(models.Q(name__iexact=identifier) | models.Q(customer_id__iexact=identifier)).first()
            if not org:
                self.stdout.write(self.style.ERROR(f'Organization "{identifier}" not found.'))
                return

            # Evaluate users to a list immediately so the list doesn't clear after org.delete()
            users = list(User.objects.filter(profile__organization=org))
            
            self.stdout.write(self.style.WARNING(f'Target Organization: {org.name} ({org.customer_id})'))
            self.stdout.write(f'Associated Users: {", ".join([u.email for u in users])}')
            
            if not force:
                confirm = input(f'Are you sure you want to delete this organization and ALL associated data? (y/N): ')
                if confirm.lower() != 'y':
                    self.stdout.write('Deletion cancelled.')
                    return

            with transaction.atomic():
                # 1. Cleanup Dashboard Data for all users in Org
                for user in users:
                    self.cleanup_user_data(user)

                # 2. Cleanup Org-level configs
                OrganizationAgentConfig.objects.filter(organization=org).delete()
                Team.objects.filter(organization=org).delete()

                # 3. Delete Organization (deleting this first releases protection on its owner)
                org_name = org.name
                org.delete()

                # 4. Delete Users (cascades to UserProfile)
                user_count = len(users)
                for user in users:
                    user.delete()

                self.stdout.write(self.style.SUCCESS(f'Successfully deleted organization "{org_name}" and {user_count} users.'))

        except Exception as e:
            raise CommandError(f'Error deleting organization: {str(e)}')

    def delete_user(self, identifier, force):
        try:
            user = User.objects.filter(models.Q(email__iexact=identifier) | models.Q(username__iexact=identifier)).first()
            if not user:
                self.stdout.write(self.style.ERROR(f'User "{identifier}" not found.'))
                return

            self.stdout.write(self.style.WARNING(f'Target User: {user.email} ({user.username})'))
            
            if not force:
                confirm = input(f'Are you sure you want to delete this user and ALL their orphaned data? (y/N): ')
                if confirm.lower() != 'y':
                    self.stdout.write('Deletion cancelled.')
                    return

            with transaction.atomic():
                self.cleanup_user_data(user)
                user.delete()
                self.stdout.write(self.style.SUCCESS(f'Successfully deleted user {user.email}.'))

        except Exception as e:
            raise CommandError(f'Error deleting user: {str(e)}')

    def cleanup_user_data(self, user):
        """Manually delete records that use DO_NOTHING or SET_NULL to ensure no orphans remain."""
        # AI BDR / Dashboard
        CallRecord.objects.filter(userId=user).delete()
        BdrCampaign.objects.filter(user=user).delete()
        BdrPitch.objects.filter(user=user).delete()
        UserAgent.objects.filter(user=user).delete()
        AgentVoice.objects.filter(user=user).delete()
        PromptTemplate.objects.filter(user=user).delete()
        EmailConfiguration.objects.filter(user=user).delete()
        SMTPServerSetting.objects.filter(user=user).delete()

        # AI Receptionist
        InboundCallRecord.objects.filter(user=user).delete()
        AIReceptionist.objects.filter(user=user).delete()
        FollowUp.objects.filter(user=user).delete()

        # CRM
        Lead.objects.filter(models.Q(owner=user) | models.Q(created_by=user)).delete()
        LeadNote.objects.filter(created_by=user).delete()
