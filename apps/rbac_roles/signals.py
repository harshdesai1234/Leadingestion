"""
Django Signals for RBAC Audit Logging.

Hooks into Django's auth login/logout and model save/delete signals
to automatically create AuditLog entries.
"""
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save, post_delete

from .models import AuditLog, Module
from .utils import get_user_role, _get_client_ip


# ─────────────────────────────────────────────────────────────────────────────
# Auth signals
# ─────────────────────────────────────────────────────────────────────────────

@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    role = get_user_role(user)
    AuditLog.objects.create(
        user=user,
        user_role=role.name if role else '',
        action_type='login',
        ip_address=_get_client_ip(request),
        success=True,
    )


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is None:
        return
    role = get_user_role(user)
    AuditLog.objects.create(
        user=user,
        user_role=role.name if role else '',
        action_type='logout',
        ip_address=_get_client_ip(request),
        success=True,
    )


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    AuditLog.objects.create(
        action_type='login_failed',
        extra_data={'username': credentials.get('email', credentials.get('username', ''))},
        ip_address=_get_client_ip(request),
        success=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Model audit signals – wire up for key CRM models
# ─────────────────────────────────────────────────────────────────────────────

def _audit_save(sender, instance, created, **kwargs):
    """Generic post_save handler – only logs if the instance has a `_audit_user`."""
    audit_user = getattr(instance, '_audit_user', None)
    if audit_user is None:
        return  # No user context; skip silent background saves

    module   = getattr(instance, '_audit_module', '')
    role     = get_user_role(audit_user)
    action   = 'create' if created else 'update'
    AuditLog.objects.create(
        user=audit_user,
        user_role=role.name if role else '',
        action_type=action,
        module=module,
        affected_record_id=str(instance.pk),
        success=True,
    )


def _audit_delete(sender, instance, **kwargs):
    """Generic post_delete handler."""
    audit_user = getattr(instance, '_audit_user', None)
    if audit_user is None:
        return

    module = getattr(instance, '_audit_module', '')
    role   = get_user_role(audit_user)
    AuditLog.objects.create(
        user=audit_user,
        user_role=role.name if role else '',
        action_type='delete',
        module=module,
        affected_record_id=str(instance.pk),
        success=True,
    )


def register_audit_signals():
    """
    Call this from AppConfig.ready() to attach audit signals to CRM models.
    Lazy imports avoid circular dependency at module load time.
    """
    from crm.models import Lead
    from dashboard.models import BdrCampaign
    try:
        from crm.models import Deal
    except ImportError:
        Deal = None

    for model, module in [
        (Lead, Module.LEADS),
        (BdrCampaign, Module.CAMPAIGNS),
    ]:
        post_save.connect(_audit_save, sender=model)
        post_delete.connect(_audit_delete, sender=model)

    if Deal:
        post_save.connect(_audit_save, sender=Deal)
        post_delete.connect(_audit_delete, sender=Deal)
