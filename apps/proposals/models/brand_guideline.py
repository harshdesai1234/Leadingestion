"""
BrandGuideline model — stores brand profiles (colours, fonts, logos) per organisation.

Each organisation can have multiple brand guidelines, with one marked as default.
These are applied to documents during generation via the brand_injector service.
"""
from django.db import models
from django.conf import settings


class BrandGuideline(models.Model):
    """Brand profile with colours, fonts, logos, and optional custom CSS."""

    organisation = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='brand_guidelines',
        help_text='The organisation this brand profile belongs to.',
    )
    name = models.CharField(
        max_length=255,
        help_text='Friendly name for this brand profile (e.g. "Corporate", "Product Launch").',
    )

    # ── Colour Palette ──────────────────────────────────────────────────────
    primary_color = models.CharField(
        max_length=7, default='#000000',
        help_text='Primary brand colour in hex (e.g. #d40000).',
    )
    secondary_color = models.CharField(
        max_length=7, default='#333333',
        help_text='Secondary brand colour in hex.',
    )
    accent_color = models.CharField(
        max_length=7, default='#ff3333',
        help_text='Accent colour in hex.',
    )
    background_color = models.CharField(
        max_length=7, default='#ffffff',
        help_text='Background colour in hex.',
    )
    text_color = models.CharField(
        max_length=7, default='#0a0a0a',
        help_text='Primary text colour in hex.',
    )

    # ── Typography ──────────────────────────────────────────────────────────
    heading_font = models.CharField(
        max_length=100, default='Inter',
        help_text='Google Font name or system font for headings.',
    )
    body_font = models.CharField(
        max_length=100, default='Inter',
        help_text='Google Font name or system font for body text.',
    )

    # ── Logo Assets ─────────────────────────────────────────────────────────
    logo = models.ImageField(
        upload_to='proposals/brands/logos/',
        null=True, blank=True,
        help_text='Primary logo (for light backgrounds).',
    )
    logo_dark = models.ImageField(
        upload_to='proposals/brands/logos/',
        null=True, blank=True,
        help_text='Logo variant for dark backgrounds.',
    )

    # ── Brand Guide Document ────────────────────────────────────────────────
    brand_guidelines_doc = models.FileField(
        upload_to='proposals/brands/docs/',
        null=True, blank=True,
        help_text='Uploaded PDF/DOCX brand guidelines document.',
    )

    # ── Custom CSS ──────────────────────────────────────────────────────────
    custom_css = models.TextField(
        blank=True, default='',
        help_text='Freeform CSS overrides applied to documents using this brand.',
    )

    # ── Flags ───────────────────────────────────────────────────────────────
    is_default = models.BooleanField(
        default=False,
        help_text='If True, this brand is pre-selected in the wizard for this org.',
    )

    # ── Audit ───────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_brand_guidelines',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        verbose_name = 'Brand Guideline'
        verbose_name_plural = 'Brand Guidelines'

    def __str__(self):
        default_tag = ' (default)' if self.is_default else ''
        return f'{self.name}{default_tag}'

    def save(self, *args, **kwargs):
        # Ensure only one default brand per organisation
        if self.is_default:
            BrandGuideline.objects.filter(
                organisation=self.organisation, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
