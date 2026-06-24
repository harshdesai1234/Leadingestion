import hashlib
import json
import re

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.conf import settings
from django.utils import timezone

_HASHER_PREFIX = re.compile(r'^\$|^[a-z0-9_]+\$')


class TenantIngestionConfig(models.Model):
    """
    Ingestion configuration per tenant (Organization).
    Contains API authentication keys, batch intervals, and action rules.
    """
    ACTION_CHOICES = [
        ('email', 'Email Campaign'),
        ('bdr_call', 'BDR Call'),
    ]

    tenant = models.OneToOneField(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='ingestion_config',
    )
    api_key = models.CharField(
        max_length=128, unique=True, db_index=True,
    )
    batch_minutes = models.PositiveSmallIntegerField(
        default=10,
        help_text="Batch processing interval in minutes (5, 10, or 15)",
    )
    default_action = models.CharField(
        max_length=12, choices=ACTION_CHOICES, default='email',
        help_text="Default action when no source-specific rule matches",
    )
    action_rules = models.TextField(
        blank=True, default='',
        help_text="JSON mapping source (e.g. linkedin) to action (e.g. bdr_call)",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Tenant Ingestion Config'
        verbose_name_plural = 'Tenant Ingestion Configs'

    def __str__(self):
        return f"{self.tenant.name} Config (Active: {self.is_active})"

    def save(self, *args, **kwargs):
        if self.api_key and not self._is_hashed(self.api_key):
            self.api_key = make_password(self.api_key)
        super().save(*args, **kwargs)

    @staticmethod
    def _is_hashed(value: str) -> bool:
        return bool(_HASHER_PREFIX.match(value))

    def verify_api_key(self, raw_key: str) -> bool:
        if self._is_hashed(self.api_key):
            return check_password(raw_key, self.api_key)
        return self.api_key == raw_key

    def get_masked_key(self) -> str:
        if self._is_hashed(self.api_key):
            return f"{self.api_key[:12]}...{self.api_key[-8:]}"
        if len(self.api_key) > 8:
            return f"{self.api_key[:4]}...{self.api_key[-4:]}"
        return "****"

    def get_action_rules(self) -> dict:
        """Parse action_rules JSON string into a dict."""
        if not self.action_rules:
            return {}
        try:
            return json.loads(self.action_rules)
        except json.JSONDecodeError:
            return {}


class RawLead(models.Model):
    """
    Stores raw, unprocessed lead payloads exactly as received from webhooks, forms, or CSVs.
    """
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_PARSED = 'parsed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PARSED, 'Parsed'),
        (STATUS_FAILED, 'Failed'),
    ]

    tenant = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='raw_leads',
    )
    source_hint = models.CharField(
        max_length=50, blank=True, default='',
        help_text="Hint of the origin (e.g. webhook, linkedin, meta)",
    )
    payload = models.TextField(
        help_text="Raw verbatim request body or row content",
    )
    payload_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True,
        help_text="SHA-256 hex digest of payload for dedup",
    )
    content_type = models.CharField(
        max_length=100, blank=True, default='',
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES,
        default=STATUS_PENDING, db_index=True,
    )
    error_detail = models.TextField(blank=True, default='')
    retry_count = models.PositiveSmallIntegerField(default=0)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Raw Lead'
        verbose_name_plural = 'Raw Leads'
        ordering = ['-received_at']

    def __str__(self):
        return f"RawLead {self.id} for {self.tenant.name} (Status: {self.status})"

    def save(self, *args, **kwargs):
        if self.payload and not self.payload_hash:
            self.payload_hash = hashlib.sha256(
                self.payload.encode('utf-8')
            ).hexdigest()
        super().save(*args, **kwargs)


class ParsedLead(models.Model):
    """
    The Unified Lead Sheet — holds structured, validated lead information
    extracted from RawLead via LLM.
    """
    ACTION_CHOICES = [
        ('email', 'Email Campaign'),
        ('bdr_call', 'BDR Call'),
        ('ai_call', 'AI Automated Call'),
    ]

    tenant = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='parsed_leads',
    )
    raw_lead = models.OneToOneField(
        RawLead,
        on_delete=models.PROTECT,
        related_name='parsed_lead',
    )
    customer_name = models.CharField(max_length=255, blank=True, default='')
    mobile_number = models.CharField(max_length=32, blank=True, default='')
    email_address = models.EmailField(blank=True, default='')
    source = models.CharField(max_length=50, blank=True, default='')
    predefined_action = models.CharField(
        max_length=12, choices=ACTION_CHOICES, blank=True, default='',
    )
    confidence_note = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Parsed Lead'
        verbose_name_plural = 'Parsed Leads'
        ordering = ['-created_at']

    def __str__(self):
        return f"ParsedLead {self.id} - {self.customer_name or self.email_address or 'Unnamed'}"
