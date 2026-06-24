"""
credit_service.py
-----------------
Central helper for all credit operations in agentyne_asoc.

Usage:
    from accounts.credit_service import deduct_credits, check_credits, get_credit_account

    # Deduct 10 credits for a 1-minute AI BDR call
    deduct_credits(org, 'ai_bdr_per_minute', 10, reference_id=str(call_id))

Design principles:
    - Never crash the caller: all functions are wrapped in try/except.
    - Phase 1: insufficient credits → log a warning, do NOT block service.
    - Phase 2: set CREDIT_ENFORCEMENT = True in settings to block on zero credits.
"""
import logging
import math
from django.conf import settings
from django.db import transaction

logger = logging.getLogger('accounts.credit_service')

# Set CREDIT_ENFORCEMENT = True in settings.py to block services when credits run out.
CREDIT_ENFORCEMENT = getattr(settings, 'CREDIT_ENFORCEMENT', False)


def get_credit_account(org):
    """
    Return (or lazily create) the OrganizationCreditAccount for org.
    If a default CreditPlan exists, the new account is pre-assigned to it.
    Returns None on any error.
    """
    try:
        from accounts.models import OrganizationCreditAccount, CreditPlan
        account, created = OrganizationCreditAccount.objects.get_or_create(
            organization=org
        )
        if created:
            default_plan = CreditPlan.objects.filter(is_default=True, is_active=True).first()
            if default_plan:
                account.assign_plan(default_plan)
            else:
                account.save()
            logger.info(f"Created new credit account for org: {org.name}")
        return account
    except Exception as e:
        logger.error(f"get_credit_account failed for org {getattr(org, 'id', '?')}: {e}")
        return None


def get_service_rate(account, service_key):
    """
    Return the credit cost for service_key from the account's assigned plan.
    Falls back to the DEFAULT_SERVICE_RATES constant.
    """
    try:
        from accounts.models import DEFAULT_SERVICE_RATES
        if account and account.plan:
            return account.plan.get_rate(service_key)
        return DEFAULT_SERVICE_RATES.get(service_key, 0)
    except Exception as e:
        logger.error(f"get_service_rate error: {e}")
        return 0


def check_credits(org, amount):
    """
    Return True if org.credit_account has at least `amount` remaining credits.
    Returns True if CREDIT_ENFORCEMENT is disabled (Phase 1 default).
    """
    if not CREDIT_ENFORCEMENT:
        return True
    try:
        account = get_credit_account(org)
        if not account:
            return True  # graceful fallback
        return account.remaining_credits >= amount
    except Exception as e:
        logger.error(f"check_credits error: {e}")
        return True


def deduct_credits(org, service_key, amount, reference_id='', notes='', user=None):
    """
    Deduct `amount` credits from org's credit account for service_key.

    - Logs a CreditTransaction regardless of whether account is valid.
    - In Phase 1, never blocks even if credits < 0.
    - Returns True on success, False on hard error.

    Args:
        org: accounts.models.Organization instance
        service_key: string key like 'ai_bdr_per_minute'
        amount: integer credits to deduct
        reference_id: optional string (e.g. call_id, lead_id)
        notes: optional string description
        user: optional User instance for attribution
    """
    if amount <= 0:
        return True
    try:
        with transaction.atomic():
            from accounts.models import OrganizationCreditAccount, CreditTransaction
            account = get_credit_account(org)
            if not account:
                logger.warning(f"No credit account for org {org.id}, skipping deduction")
                return False

            remaining_before = account.remaining_credits
            if CREDIT_ENFORCEMENT and remaining_before < amount:
                logger.warning(
                    f"Org {org.name} has insufficient credits: {remaining_before} < {amount} "
                    f"for {service_key}"
                )
                return False

            # --- Per-Feature Limit Check ---
            if account.plan and account.plan.feature_limits:
                limit = account.plan.feature_limits.get(service_key)
                if limit is not None:
                    current_usage = (account.feature_usage or {}).get(service_key, 0)
                    if current_usage + amount > limit:
                        logger.warning(
                            f"Org {org.name} hit feature limit for {service_key}: "
                            f"{current_usage} + {amount} > {limit}"
                        )
                        if CREDIT_ENFORCEMENT:
                            return False

            # Atomically increment used_credits and feature_usage
            new_feature_usage = account.feature_usage or {}
            new_feature_usage[service_key] = new_feature_usage.get(service_key, 0) + amount
            
            OrganizationCreditAccount.objects.filter(pk=account.pk).update(
                used_credits=account.used_credits + amount,
                feature_usage=new_feature_usage
            )

            CreditTransaction.objects.create(
                account=account,
                service=service_key,
                action=CreditTransaction.ACTION_DEDUCT,
                credits=-amount,
                user=user,
                reference_id=reference_id or '',
                notes=notes or f"Deducted {amount} credits for {service_key}",
            )

            logger.debug(
                f"Deducted {amount} credits from {org.name} for {service_key}. "
                f"Remaining: {remaining_before - amount}"
            )
            return True
    except Exception as e:
        logger.error(f"deduct_credits failed for org {getattr(org, 'id', '?')}: {e}")
        return False


def add_credits(org, amount, notes='', action='add', user=None):
    """
    Add `amount` credits to org's credit account (manual top-up or adjustment).

    Args:
        org: Organization instance
        amount: positive integer
        notes: optional description
        action: 'add' or 'adjustment'
        user: optional User instance for attribution
    """
    if amount <= 0:
        return False
    try:
        with transaction.atomic():
            from accounts.models import OrganizationCreditAccount, CreditTransaction
            account = get_credit_account(org)
            if not account:
                return False

            OrganizationCreditAccount.objects.filter(pk=account.pk).update(
                total_credits=account.total_credits + amount
            )

            CreditTransaction.objects.create(
                account=account,
                service='manual',
                action=action,
                credits=amount,
                user=user,
                notes=notes or f"Added {amount} credits manually",
            )
            logger.info(f"Added {amount} credits to {org.name}")
            return True
    except Exception as e:
        logger.error(f"add_credits failed for org {getattr(org, 'id', '?')}: {e}")
        return False


def deduct_for_call_minutes(org, service_key, duration_seconds, call_id='', user=None):
    """
    Convenience wrapper: deduct credits based on a call's duration in seconds.
    Rounds up to the nearest whole minute and charges per-minute rate.

    Args:
        org: Organization instance
        service_key: 'ai_bdr_per_minute' or 'ai_receptionist_per_minute'
        duration_seconds: int (call duration in seconds)
        call_id: optional string reference
        user: optional User instance for attribution
    """
    try:
        if not duration_seconds or duration_seconds <= 0:
            return True

        account = get_credit_account(org)
        rate_per_minute = get_service_rate(account, service_key)
        minutes = math.ceil(duration_seconds / 60)
        total_credits = minutes * rate_per_minute

        notes = f"{minutes} min × {rate_per_minute} credits/min = {total_credits} credits"
        return deduct_credits(
            org, service_key, total_credits,
            reference_id=str(call_id),
            notes=notes,
            user=user
        )
    except Exception as e:
        logger.error(f"deduct_for_call_minutes error: {e}")
        return False
