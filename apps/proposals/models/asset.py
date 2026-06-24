"""
Asset model — uploaded reference documents, images, and logos.

Assets can be attached to a specific document (document-level) or shared
across the organisation (org-level, when document FK is null).
Text is extracted from uploaded PDFs/DOCX files for context injection into AI prompts.
"""
from django.db import models
from django.conf import settings


class Asset(models.Model):
    """Uploaded reference doc, image, or logo for proposals."""

    # ── Asset Types ─────────────────────────────────────────────────────────
    TYPE_REFERENCE_DOC = 'REFERENCE_DOC'
    TYPE_LOGO = 'LOGO'
    TYPE_IMAGE = 'IMAGE'
    TYPE_BRAND_GUIDE = 'BRAND_GUIDE'
    TYPE_OTHER = 'OTHER'

    ASSET_TYPE_CHOICES = [
        (TYPE_REFERENCE_DOC, 'Reference Document'),
        (TYPE_LOGO, 'Logo'),
        (TYPE_IMAGE, 'Image'),
        (TYPE_BRAND_GUIDE, 'Brand Guide'),
        (TYPE_OTHER, 'Other'),
    ]

    # ── Relationships ───────────────────────────────────────────────────────
    document = models.ForeignKey(
        'proposals.Document',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='assets',
        help_text='Document this asset is attached to (null = org-level reusable asset).',
    )
    organisation = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='proposal_assets',
        help_text='The organisation this asset belongs to.',
    )

    # ── Asset Data ──────────────────────────────────────────────────────────
    asset_type = models.CharField(
        max_length=20, choices=ASSET_TYPE_CHOICES, default=TYPE_OTHER,
        help_text='Type classification of this asset.',
    )
    file = models.FileField(
        upload_to='proposals/assets/',
        help_text='The uploaded file.',
    )
    original_filename = models.CharField(
        max_length=500, blank=True, default='',
        help_text='Original filename as uploaded by the user.',
    )
    extracted_text = models.TextField(
        blank=True, default='',
        help_text='Text extracted from PDF/DOCX references (used in AI prompts).',
    )
    description = models.CharField(
        max_length=500, blank=True, default='',
        help_text='Brief description of this asset.',
    )

    # ── Audit ───────────────────────────────────────────────────────────────
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='uploaded_proposal_assets',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Asset'
        verbose_name_plural = 'Assets'

    def __str__(self):
        return f'{self.original_filename or self.file.name} ({self.get_asset_type_display()})'
