from django.db import models
from django.contrib.auth.models import User
import uuid
import secrets
import string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


def generate_customer_id():
    """Generate a unique customer ID in AGT-XXXXXXXX format."""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(8))
    return f'AGT-{suffix}'


class Organization(models.Model):
    """
    Represents a company/customer account.
    All users within the same org share the same data workspace.
    """
    customer_id = models.CharField(
        max_length=20, unique=True, default=generate_customer_id,
        help_text="Unique customer identifier (e.g. AGT-K3M9PQ2R)"
    )
    name = models.CharField(max_length=255, help_text="Company name")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_organizations',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'

    def get_users(self):
        """Return all users that belong to this organization."""
        return User.objects.filter(profile__organization=self)

    def get_user_ids(self):
        """Return a list of user IDs that belong to this organization."""
        return list(self.get_users().values_list('id', flat=True))

    def get_member_count(self):
        return self.members.count()

    def __str__(self):
        return f"{self.name} ({self.customer_id})"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('member', 'Member'),
        ('superadmin', 'Super Admin'),  # kept for backward compat
    ]

    # ── RBAC ─────────────────────────────────────────────────────────────────
    # New authoritative role & team fields – set by org-admin on invite accept.
    rbac_role = models.ForeignKey(
        'rbac_roles.Role',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='user_profiles',
        help_text="RBAC role assigned to this user within their organization.",
    )
    teams = models.ManyToManyField(
        'rbac_roles.Team',
        blank=True,
        related_name='members',
        help_text="Teams this user belongs to (supports multiple teams for cross-team collaboration).",
    )
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    userid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    mobile_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    mobile_number_verified = models.BooleanField(default=False)
    country = models.CharField(max_length=100, null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    # Organization (company-level isolation for SaaS multi-tenancy)
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='members',
        help_text="The company/organization this user belongs to"
    )
    # Legacy plain-text org fields (kept for backward compat, superseded by organization FK)
    org_name = models.CharField(max_length=255, null=True, blank=True)
    org_id = models.CharField(max_length=255, null=True, blank=True)
    # OTP verification attempt tracking
    otp_attempts_count = models.IntegerField(default=0, help_text="Number of OTP verification attempts")
    otp_blocked_until = models.DateTimeField(null=True, blank=True, help_text="Timestamp until which OTP sending is blocked")
    is_otp_blocked = models.BooleanField(default=False, help_text="Flag indicating if user is blocked from requesting OTPs")
    
    # product tracking
    # product = models.JSONField(default=dict, blank=True)  # Store selected features as JSON
    ai_bdr_activated = models.BooleanField(default=False, help_text="Flag indicating if AI BDR is activated")
    ai_bdr_activated_date = models.DateTimeField(null=True, blank=True, help_text="Timestamp of AI BDR activation")
    ai_bdr_deactivated_date = models.DateTimeField(null=True, blank=True, help_text="Timestamp of AI BDR deactivation")
    transcription_activated = models.BooleanField(default=False, help_text="Flag indicating if transcription is activated")
    transcription_activated_date = models.DateTimeField(null=True, blank=True, help_text="Timestamp of transcription activation")
    transcription_deactivated_date = models.DateTimeField(null=True, blank=True, help_text="Timestamp of transcription deactivation")   
    pishing_activated = models.BooleanField(default=False, help_text="Flag indicating if pishing is activated")
    pishing_activated_date = models.DateTimeField(null=True, blank=True, help_text="Timestamp of pishing activation")
    pishing_deactivated_date = models.DateTimeField(null=True, blank=True, help_text="Timestamp of pishing deactivation")
    ai_rec_activated = models.BooleanField(default=False, help_text="Flag indicating if AI Receptionist is activated")
    ai_rec_activated_date = models.DateTimeField(null=True, blank=True, help_text="Timestamp of AI Receptionist activation")
    ai_rec_deactivated_date = models.DateTimeField(null=True, blank=True, help_text="Timestamp of AI Receptionist deactivation")

    def __str__(self):
        return self.user.username
        
    def reset_otp_attempts(self):
        """Reset OTP attempts counter and unblock user"""
        self.otp_attempts_count = 0
        self.is_otp_blocked = False
        self.otp_blocked_until = None
        self.save()
        
    def increment_otp_attempts(self):
        """Increment OTP attempts counter and block if limit reached"""
        self.otp_attempts_count += 1
        if self.otp_attempts_count >= 3:
            self.is_otp_blocked = True
            # Block for 24 hours
            self.otp_blocked_until = timezone.now() + timedelta(hours=24)
        self.save()
        
    def check_otp_blocked_status(self):
        """Check if user is still blocked or if block period has expired"""
        if self.is_otp_blocked and self.otp_blocked_until:
            if timezone.now() > self.otp_blocked_until:
                # Block period has expired, reset attempts
                self.reset_otp_attempts()
                return False
            return True
        return False
        
    def get_remaining_attempts(self):
        """Get remaining OTP attempts before blocking"""
        if self.is_otp_blocked:
            return 0
        return max(0, 3 - self.otp_attempts_count)


class PasswordSetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Token valid for 7 days
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at


class Invitation(models.Model):
    """
    Represents a pending invite for a user to join an organization.
    Flow:
      1. Owner/admin sends invite → Invitation created, email sent.
      2. Invitee clicks link → if new user, org is auto-assigned on signup;
         if existing user, org is linked immediately after login.
    """
    STATUS_PENDING  = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_EXPIRED  = 'expired'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_EXPIRED,  'Expired'),
    ]

    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations',
    )
    email = models.EmailField(help_text="Email address of the person being invited")
    rbac_role = models.ForeignKey(
        'rbac_roles.Role',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='invitations',
        help_text="RBAC role to assign when the invitee joins. Defaults to Sales Rep.",
    )
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='accepted_invitations',
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    expires_at  = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Invitation'
        verbose_name_plural = 'Invitations'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.status == self.STATUS_PENDING and timezone.now() < self.expires_at

    def mark_accepted(self, user):
        self.status = self.STATUS_ACCEPTED
        self.accepted_by = user
        self.accepted_at = timezone.now()
        self.save()

    def get_accept_url(self):
        from django.urls import reverse
        return reverse('accept_invite', kwargs={'token': str(self.token)})

    def __str__(self):
        return f"Invite {self.email} → {self.organization.name} ({self.status})"


class Plan(models.Model):
    PLAN_TYPES = [
        ('FREE', 'Free'),
        ('PRO', 'Pro'),
        ('BUSINESS', 'Business'),
        ('ENTERPRISE', 'Enterprise'),
    ]
    
    BILLING_CYCLES = (
        ('MONTHLY', 'Monthly'),
        ('YEARLY', 'Yearly')
    )
    service_name = models.CharField(max_length=100,default="transcription")
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    minutes_included = models.IntegerField(help_text="Minutes per month/user")
    is_most_popular = models.BooleanField(default=False)
    yearly_discount_percentage = models.IntegerField(default=20)
    
    def __str__(self):
        return f"{self.get_plan_type_display()} - {self.get_billing_cycle_display()}"
    
    class Meta:
        unique_together = ['plan_type', 'billing_cycle']

class PlanFeature(models.Model):
    plan = models.ForeignKey(Plan, related_name='features', on_delete=models.CASCADE)
    feature_name = models.CharField(max_length=200)
    is_included = models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True)
    order = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.feature_name} - {'✓' if self.is_included else '✗'}"
    
    class Meta:
        ordering = ['order']

class UserPlan(models.Model):
    PLAN_STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plans')
    # product = models.ForeignKey('payment.Product', on_delete=models.SET_NULL, null=True, related_name='user_plans')
    # payment = models.ForeignKey('payment.Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='user_plans')
    status = models.CharField(max_length=20, choices=PLAN_STATUS_CHOICES, default='pending')
    features = models.JSONField(default=dict, blank=True)  # Store selected features as JSON
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_trial = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - Plan"
    
    def is_active(self):
        if self.status != 'active':
            return False
        if self.end_date and timezone.now() > self.end_date:
            self.status = 'expired'
            self.save()
            return False
        return True
    
    def days_remaining(self):
        if not self.end_date:
            return None
        if timezone.now() > self.end_date:
            return 0
        return (self.end_date - timezone.now()).days


# ---------------------------------------------------------------------------
#  Credit-Based Usage System
# ---------------------------------------------------------------------------

DEFAULT_SERVICE_RATES = {
    "ai_bdr_per_minute": 10,
    "ai_receptionist_per_minute": 10,
    "lead_enrichment_email": 1,
    "lead_enrichment_phone": 10,
    "email_generation": 1,
    "slide_per_slide": 10,
    "note_taker_per_30min": 100,
}


class CreditPlan(models.Model):
    """
    Defines a named credit plan with per-service credit costs.
    Admin can create multiple plans and assign any plan to any organization.
    service_rates is a JSONField keyed by service name (see DEFAULT_SERVICE_RATES).
    """
    name = models.CharField(max_length=100, help_text="Plan name, e.g. 'Starter', 'Growth'")
    description = models.TextField(blank=True, help_text="Optional description of this plan")
    total_credits = models.PositiveIntegerField(
        default=1000,
        help_text="Total credits included in this plan (1 USD = 100 credits)"
    )
    validity_days = models.PositiveIntegerField(
        default=30,
        help_text="How many days this plan remains valid (30 = monthly, 365 = yearly)"
    )
    service_rates = models.JSONField(
        default=dict,
        help_text="Per-service credit costs. Example: {'ai_bdr_per_minute': 10}"
    )
    feature_limits = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional per-service usage caps (for Free Plans). Example: {'ai_bdr_per_minute': 200}"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="If True, new organizations are automatically assigned this plan"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Credit Plan'
        verbose_name_plural = 'Credit Plans'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.total_credits} credits / {self.validity_days}d)"

    def save(self, *args, **kwargs):
        # Ensure only one plan is marked as default at a time
        if self.is_default:
            CreditPlan.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)
        # Seed default service rates if none provided
        if not self.service_rates:
            self.service_rates = DEFAULT_SERVICE_RATES.copy()
        super().save(*args, **kwargs)

    def get_rate(self, service_key):
        """Return credit cost for a given service key, falling back to default."""
        return self.service_rates.get(service_key, DEFAULT_SERVICE_RATES.get(service_key, 0))


class OrganizationCreditAccount(models.Model):
    """
    One credit wallet per organization.
    Tracks total/used credits and which plan is assigned.
    """
    organization = models.OneToOneField(
        'Organization',
        on_delete=models.CASCADE,
        related_name='credit_account',
    )
    plan = models.ForeignKey(
        CreditPlan,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='org_accounts',
        help_text="The credit plan assigned to this organization"
    )
    total_credits = models.PositiveIntegerField(
        default=0,
        help_text="Total credits allocated (copied from plan on assignment, can be overridden)"
    )
    used_credits = models.PositiveIntegerField(
        default=0,
        help_text="Credits consumed so far"
    )
    feature_usage = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tracks credit consumption per service to enforce feature_limits"
    )
    validity_till = models.DateField(
        null=True, blank=True,
        help_text="Date until which this credit allocation is valid"
    )
    notes = models.TextField(blank=True, help_text="Internal admin notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Organization Credit Account'
        verbose_name_plural = 'Organization Credit Accounts'

    def __str__(self):
        return f"{self.organization.name} — {self.remaining_credits}/{self.total_credits} credits"

    @property
    def remaining_credits(self):
        return max(0, self.total_credits - self.used_credits)

    @property
    def usage_percentage(self):
        if self.total_credits == 0:
            return 0
        return min(100, round((self.used_credits / self.total_credits) * 100))

    @property
    def is_valid(self):
        """True if account is within validity window (or no expiry set)."""
        if not self.validity_till:
            return True
        from django.utils import timezone
        return timezone.now().date() <= self.validity_till

    def assign_plan(self, plan, validity_till=None):
        """Assign a plan to this account, copying credit amount and computing validity."""
        from django.utils import timezone
        from datetime import timedelta
        self.plan = plan
        self.total_credits = plan.total_credits
        if validity_till:
            self.validity_till = validity_till
        else:
            self.validity_till = (timezone.now() + timedelta(days=plan.validity_days)).date()
        self.save()


class CreditTransaction(models.Model):
    """
    Immutable audit log of every credit addition or deduction on an org account.
    """
    ACTION_DEDUCT = 'deduct'
    ACTION_ADD = 'add'
    ACTION_ADJUSTMENT = 'adjustment'
    ACTION_CHOICES = [
        (ACTION_DEDUCT, 'Deduction'),
        (ACTION_ADD, 'Addition'),
        (ACTION_ADJUSTMENT, 'Manual Adjustment'),
    ]

    account = models.ForeignKey(
        OrganizationCreditAccount,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    service = models.CharField(
        max_length=100,
        blank=True,
        help_text="Service key, e.g. 'ai_bdr', 'ai_receptionist', 'lead_enrichment_email'"
    )
    user = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='credit_transactions',
        help_text="The user who initiated this transaction"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default=ACTION_DEDUCT)
    # Positive = credit added, Negative = credit deducted
    credits = models.IntegerField(
        help_text="Credits changed. Negative for deductions, positive for additions."
    )
    reference_id = models.CharField(
        max_length=255, blank=True,
        help_text="Optional reference, e.g. call_id or lead_id"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Credit Transaction'
        verbose_name_plural = 'Credit Transactions'
        ordering = ['-created_at']

    def __str__(self):
        direction = '+' if self.credits >= 0 else ''
        return f"{self.account.organization.name} | {self.service} | {direction}{self.credits} credits"

class SignupRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    mobile_number = models.CharField(max_length=15)
    organization_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Signup Request'
        verbose_name_plural = 'Signup Requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.organization_name})"

class SignupNotificationEmail(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Signup Notification Email'
        verbose_name_plural = 'Signup Notification Emails'
    
    def __str__(self):
        return self.email
