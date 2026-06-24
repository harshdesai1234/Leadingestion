from django.contrib import admin
from django.urls import path
from django.utils.html import format_html
from .models import Organization, UserProfile, Plan, PlanFeature, UserPlan, Invitation, SignupRequest, SignupNotificationEmail


# ─── Signup Request ───────────────────────────────────────────────────────────

@admin.register(SignupRequest)
class SignupRequestAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'mobile_number', 'organization_name', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'organization_name']
    ordering = ['-created_at']
    actions = ['approve_requests', 'reject_requests']

    def approve_requests(self, request, queryset):
        queryset.update(status='approved')
    approve_requests.short_description = "Mark selected requests as Approved"

    def reject_requests(self, request, queryset):
        queryset.update(status='rejected')
    reject_requests.short_description = "Mark selected requests as Rejected"

@admin.register(SignupNotificationEmail)
class SignupNotificationEmailAdmin(admin.ModelAdmin):
    list_display = ['email', 'is_active']
    list_filter = ['is_active']
    search_fields = ['email']


# ─── Custom Admin Site to inject extra URL + sidebar link ─────────────────────

class AccountsAdminMixin:
    """
    Mixin added to the default AdminSite so we can register
    a custom URL for the 'Create Managed User' page.
    """
    def get_urls(self):
        from .admin_views import create_managed_user
        custom = [
            path(
                'accounts/create-user/',
                self.admin_site.admin_view(create_managed_user),
                name='create_managed_user',
            ),
        ]
        return custom + super().get_urls()


# ─── Organization ─────────────────────────────────────────────────────────────

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display   = ['customer_id', 'name', 'owner_email', 'member_count', 'is_active', 'created_at']
    list_filter    = ['is_active', 'created_at']
    search_fields  = ['customer_id', 'name', 'owner__email']
    readonly_fields = ['customer_id', 'created_at', 'updated_at']
    ordering       = ['-created_at']

    def owner_email(self, obj):
        return obj.owner.email
    owner_email.short_description = 'Owner Email'

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'

    # Quick-link to the create user page from the org list
    def get_urls(self):
        from .admin_views import create_managed_user
        custom = [
            path(
                'create-user/',
                self.admin_site.admin_view(create_managed_user),
                name='create_managed_user',
            ),
        ]
        return custom + super().get_urls()

    # Show the link in the changelist page header
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['create_user_url'] = '/admin/accounts/create-user/'
        return super().changelist_view(request, extra_context=extra_context)


# ─── Invitation ───────────────────────────────────────────────────────────────

@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display   = ['email', 'organization', 'invited_by', 'status', 'created_at', 'expires_at', 'accepted_by']
    list_filter    = ['status', 'created_at']
    search_fields  = ['email', 'organization__name', 'organization__customer_id', 'invited_by__email']
    readonly_fields = ['token', 'created_at', 'accepted_at']
    ordering       = ['-created_at']


# ─── UserProfile ──────────────────────────────────────────────────────────────

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display   = ['user', 'org_link', 'role', 'email_verified', 'is_active_user', 'ai_bdr_activated', 'ai_rec_activated']
    list_filter    = ['role', 'email_verified', 'ai_bdr_activated', 'ai_rec_activated']
    search_fields  = ['user__email', 'user__username', 'organization__customer_id', 'organization__name']
    raw_id_fields  = ['user', 'organization']

    def org_link(self, obj):
        if obj.organization:
            return format_html(
                '<span style="font-family:monospace;font-size:11px;background:#f3f4f6;'
                'padding:2px 6px;border-radius:4px;color:#4f46e5;">{}</span> {}',
                obj.organization.customer_id,
                obj.organization.name,
            )
        return '—'
    org_link.short_description = 'Organization'

    def is_active_user(self, obj):
        active = obj.user.is_active
        color  = '#16a34a' if active else '#d97706'
        label  = 'Active' if active else 'Pending'
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, label)
    is_active_user.short_description = 'Account'
