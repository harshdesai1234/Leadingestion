"""
DocumentSection model — ordered sections within a document.

Each section represents a content block (cover, executive summary, body section,
table, image, pricing, timeline, appendix) within a Document. Sections are
ordered and can be individually edited, regenerated, or reordered.
"""
from django.db import models
from django.conf import settings


class DocumentSection(models.Model):
    """A content section within a Document, ordered by position."""

    # ── Section Types ───────────────────────────────────────────────────────
    TYPE_COVER = 'COVER'
    TYPE_EXECUTIVE_SUMMARY = 'EXECUTIVE_SUMMARY'
    TYPE_SECTION = 'SECTION'
    TYPE_TABLE = 'TABLE'
    TYPE_IMAGE = 'IMAGE'
    TYPE_PRICING = 'PRICING'
    TYPE_TIMELINE = 'TIMELINE'
    TYPE_APPENDIX = 'APPENDIX'

    SECTION_TYPE_CHOICES = [
        (TYPE_COVER, 'Cover Page'),
        (TYPE_EXECUTIVE_SUMMARY, 'Executive Summary'),
        (TYPE_SECTION, 'Section'),
        (TYPE_TABLE, 'Table'),
        (TYPE_IMAGE, 'Image'),
        (TYPE_PRICING, 'Pricing'),
        (TYPE_TIMELINE, 'Timeline'),
        (TYPE_APPENDIX, 'Appendix'),
    ]

    # ── Relationships ───────────────────────────────────────────────────────
    document = models.ForeignKey(
        'proposals.Document',
        on_delete=models.CASCADE,
        related_name='sections',
        help_text='The document this section belongs to.',
    )

    # ── Position & Type ─────────────────────────────────────────────────────
    order = models.IntegerField(
        default=0,
        help_text='Display order within the document (0-indexed).',
    )
    section_type = models.CharField(
        max_length=30, choices=SECTION_TYPE_CHOICES, default=TYPE_SECTION,
        help_text='Semantic type of this section.',
    )
    title = models.CharField(
        max_length=500, blank=True, default='',
        help_text='Section heading.',
    )

    # ── Content ─────────────────────────────────────────────────────────────
    content_html = models.TextField(
        blank=True, default='',
        help_text='Editable rich HTML content for this section.',
    )
    content_raw = models.TextField(
        blank=True, default='',
        help_text='Original AI-generated text (for diff/reset functionality).',
    )

    # ── Image ───────────────────────────────────────────────────────────────
    image = models.ImageField(
        upload_to='proposals/sections/images/',
        null=True, blank=True,
        help_text='AI-generated or user-uploaded image for this section.',
    )
    image_prompt = models.TextField(
        blank=True, default='',
        help_text='Prompt used to generate the image (for regeneration).',
    )

    # ── Flags ───────────────────────────────────────────────────────────────
    is_visible = models.BooleanField(
        default=True,
        help_text='If False, section is hidden in the editor and exports.',
    )
    ai_generated = models.BooleanField(
        default=False,
        help_text='True if this section was created by AI generation.',
    )

    # ── Audit ───────────────────────────────────────────────────────────────
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='edited_proposal_sections',
        help_text='Last user who edited this section.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['document', 'order']
        verbose_name = 'Document Section'
        verbose_name_plural = 'Document Sections'

    def __str__(self):
        return f'[{self.order}] {self.title or self.get_section_type_display()} — {self.document.title}'
