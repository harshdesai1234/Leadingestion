"""
Document model — the core proposal/flyer/brochure/datasheet entity.

Each document belongs to an organisation (tenant isolation), is created via the
wizard, and edited in the Word-style editor. Status tracks it through the
lifecycle from DRAFT → GENERATING → REVIEW → APPROVED → EXPORTED.
"""
from django.db import models
from django.conf import settings


class Document(models.Model):
    """Core document model for proposals, flyers, brochures, etc."""

    # ── Document Types ──────────────────────────────────────────────────────
    TYPE_PROPOSAL = 'PROPOSAL'
    TYPE_FLYER = 'FLYER'
    TYPE_BROCHURE = 'BROCHURE'
    TYPE_DATASHEET = 'DATASHEET'
    TYPE_REPORT = 'REPORT'
    TYPE_CUSTOM = 'CUSTOM'

    DOC_TYPE_CHOICES = [
        (TYPE_PROPOSAL, 'Proposal'),
        (TYPE_FLYER, 'Flyer'),
        (TYPE_BROCHURE, 'Brochure'),
        (TYPE_DATASHEET, 'Datasheet'),
        (TYPE_REPORT, 'Report'),
        (TYPE_CUSTOM, 'Custom'),
    ]

    # ── Content Modes ───────────────────────────────────────────────────────
    MODE_TEXT_ONLY = 'TEXT_ONLY'
    MODE_TEXT_AND_IMAGES = 'TEXT_AND_IMAGES'
    MODE_TEXT_AND_UPLOADS = 'TEXT_AND_UPLOADS'

    CONTENT_MODE_CHOICES = [
        (MODE_TEXT_ONLY, 'Text Only'),
        (MODE_TEXT_AND_IMAGES, 'Text + AI Images'),
        (MODE_TEXT_AND_UPLOADS, 'Text + Upload Images'),
    ]

    # ── Status Flow ─────────────────────────────────────────────────────────
    STATUS_DRAFT = 'DRAFT'
    STATUS_GENERATING = 'GENERATING'
    STATUS_REVIEW = 'REVIEW'
    STATUS_APPROVED = 'APPROVED'
    STATUS_EXPORTED = 'EXPORTED'
    STATUS_IN_REVIEW = 'IN_REVIEW'
    STATUS_SENT = 'SENT'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_GENERATING, 'Generating'),
        (STATUS_REVIEW, 'Review'),
        (STATUS_IN_REVIEW, 'In Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_EXPORTED, 'Exported'),
        (STATUS_SENT, 'Sent'),
    ]

    # ── Tenant Isolation ────────────────────────────────────────────────────
    organisation = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='proposals_documents',
        help_text='The organisation this document belongs to.',
    )

    # ── Core Fields ─────────────────────────────────────────────────────────
    title = models.CharField(
        max_length=500,
        help_text='Document title (e.g. "Partnership Proposal for ARC Care").',
    )
    doc_type = models.CharField(
        max_length=20, choices=DOC_TYPE_CHOICES, default=TYPE_PROPOSAL,
        help_text='Type of document.',
    )
    content_mode = models.CharField(
        max_length=20, choices=CONTENT_MODE_CHOICES, default=MODE_TEXT_ONLY,
        help_text='How content is generated (text-only, text+AI images, text+uploads).',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT,
        help_text='Current lifecycle status.',
    )

    # ── Brand ───────────────────────────────────────────────────────────────
    brand_guideline = models.ForeignKey(
        'proposals.BrandGuideline',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='documents',
        help_text='Brand profile applied to this document.',
    )

    # ── Recipient Info ──────────────────────────────────────────────────────
    recipient_name = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Name of the recipient (e.g. "ARC Care Solutions").',
    )
    recipient_context = models.TextField(
        blank=True, default='',
        help_text='Context notes from the wizard intake about the recipient.',
    )

    # ── Content ─────────────────────────────────────────────────────────────
    generated_html = models.TextField(
        blank=True, default='',
        help_text='Final rendered HTML content of the full document.',
    )
    wizard_answers = models.JSONField(
        default=dict, blank=True,
        help_text='All wizard Q&A stored as JSON for regeneration/audit.',
    )

    # ── Metrics ─────────────────────────────────────────────────────────────
    word_count = models.IntegerField(
        default=0,
        help_text='Approximate word count of the document.',
    )
    version = models.IntegerField(
        default=1,
        help_text='Document version — incremented on each regeneration.',
    )

    # ── Ownership & Assignment ──────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_proposals',
        help_text='User who created this document.',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_proposals',
        help_text='User this document is assigned to for collaboration.',
    )

    # ── Timestamps ──────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        return f'{self.title} ({self.get_doc_type_display()}) — {self.get_status_display()}'

    @property
    def section_count(self):
        return self.sections.count()

    @property
    def is_editable(self):
        """Document is editable in DRAFT or REVIEW status."""
        return self.status in (self.STATUS_DRAFT, self.STATUS_REVIEW)
