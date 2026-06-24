"""
AIJob model — tracks async AI generation jobs.

Every AI call (text generation, image generation) is logged as an AIJob
with the prompt used, result data, token count, duration, and status.
This provides an audit trail and enables async polling via HTMX.
"""
from django.db import models
from django.conf import settings


class AIJob(models.Model):
    """Tracks a single AI generation job (text or image)."""

    # ── Job Types ───────────────────────────────────────────────────────────
    JOB_FULL_DOCUMENT = 'FULL_DOCUMENT'
    JOB_SECTION_TEXT = 'SECTION_TEXT'
    JOB_SECTION_IMAGE = 'SECTION_IMAGE'
    JOB_SELECTION_IMAGE = 'SELECTION_IMAGE'
    JOB_INTAKE_QUESTIONS = 'INTAKE_QUESTIONS'

    JOB_TYPE_CHOICES = [
        (JOB_FULL_DOCUMENT, 'Full Document Generation'),
        (JOB_SECTION_TEXT, 'Section Text Generation'),
        (JOB_SECTION_IMAGE, 'Section Image Generation'),
        (JOB_SELECTION_IMAGE, 'Selection Image Generation'),
        (JOB_INTAKE_QUESTIONS, 'Intake Questions Generation'),
    ]

    # ── Status ──────────────────────────────────────────────────────────────
    STATUS_PENDING = 'PENDING'
    STATUS_RUNNING = 'RUNNING'
    STATUS_COMPLETE = 'COMPLETE'
    STATUS_FAILED = 'FAILED'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_FAILED, 'Failed'),
    ]

    # ── Relationships ───────────────────────────────────────────────────────
    document = models.ForeignKey(
        'proposals.Document',
        on_delete=models.CASCADE,
        related_name='ai_jobs',
        help_text='The document this AI job is for.',
    )

    # ── Job Details ─────────────────────────────────────────────────────────
    job_type = models.CharField(
        max_length=30, choices=JOB_TYPE_CHOICES,
        help_text='What type of AI generation this job performs.',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
        help_text='Current status of this AI job.',
    )
    prompt_used = models.TextField(
        blank=True, default='',
        help_text='The full prompt sent to the AI model.',
    )
    result_data = models.JSONField(
        default=dict, blank=True,
        help_text='Raw AI response data stored as JSON.',
    )
    error_message = models.TextField(
        blank=True, default='',
        help_text='Error message if the job failed.',
    )

    # ── Model & Metrics ─────────────────────────────────────────────────────
    model_used = models.CharField(
        max_length=100, blank=True, default='',
        help_text='The AI model name used (e.g. "claude-sonnet-4-5").',
    )
    tokens_used = models.IntegerField(
        default=0,
        help_text='Total tokens consumed by this AI call.',
    )
    duration_seconds = models.FloatField(
        default=0.0,
        help_text='Wall-clock time for the AI call in seconds.',
    )

    # ── Audit ───────────────────────────────────────────────────────────────
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='triggered_ai_jobs',
        help_text='User who triggered this AI generation.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI Job'
        verbose_name_plural = 'AI Jobs'

    def __str__(self):
        return f'{self.get_job_type_display()} — {self.get_status_display()} ({self.document.title})'

    @property
    def is_complete(self):
        return self.status == self.STATUS_COMPLETE

    @property
    def is_failed(self):
        return self.status == self.STATUS_FAILED

    @property
    def is_running(self):
        return self.status in (self.STATUS_PENDING, self.STATUS_RUNNING)
