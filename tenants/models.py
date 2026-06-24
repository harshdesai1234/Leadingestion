"""
Tenant models - Placeholder for multi-tenancy support.

This is a simplified version for single-tenant deployment.
For full multi-tenancy, implement proper tenant isolation.
"""

from django.db import models
from django.conf import settings


class Tenant(models.Model):
    """
    Concrete Tenant model for multi-tenancy support.
    Referenced by agents and other tenant-aware models.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_tenants',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'

    def __str__(self):
        return self.name


class TenantAwareModel(models.Model):
    """
    Abstract base model for tenant-aware models.
    
    In a full multi-tenant system, this would include tenant foreign key
    and custom managers for tenant isolation. For now, it's a simple
    abstract model that can be extended later.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='%(class)s_items',
    )
    
    # Common fields for all tenant-aware models
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        verbose_name="Created By"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated',
        verbose_name="Updated By"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        
    def save(self, *args, **kwargs):
        """Override save to handle tenant-specific logic if needed"""
        super().save(*args, **kwargs)
