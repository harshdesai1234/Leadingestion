"""
ModuleSettings model — per-tenant AI model configuration.

Each organisation gets one ModuleSettings record that controls which AI
models are used for text and image generation, max token limits, and
whether async generation is enabled.
"""
from django.db import models
from proposals.config import PROPOSALS_CONFIG


class ModuleSettings(models.Model):
    """Per-organisation AI model settings for the Proposal Builder."""

    # ── Provider Choices ────────────────────────────────────────────────────
    PROVIDER_ANTHROPIC = 'ANTHROPIC'
    PROVIDER_OPENAI = 'OPENAI'
    PROVIDER_GOOGLE = 'GOOGLE'
    PROVIDER_STABILITY = 'STABILITY'

    TEXT_PROVIDER_CHOICES = [
        (PROVIDER_ANTHROPIC, 'Anthropic (Claude)'),
        (PROVIDER_OPENAI, 'OpenAI (GPT)'),
        (PROVIDER_GOOGLE, 'Google (Gemini)'),
    ]

    IMAGE_PROVIDER_CHOICES = [
        (PROVIDER_GOOGLE, 'Google (Gemini)'),
        (PROVIDER_OPENAI, 'OpenAI (DALL-E)'),
        (PROVIDER_STABILITY, 'Stability AI'),
    ]

    # ── Tenant ──────────────────────────────────────────────────────────────
    organisation = models.OneToOneField(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='proposal_settings',
        help_text='The organisation these settings belong to.',
    )

    # ── Text Generation ─────────────────────────────────────────────────────
    text_model_provider = models.CharField(
        max_length=20, choices=TEXT_PROVIDER_CHOICES,
        default=PROVIDER_ANTHROPIC,
        help_text='AI provider for text generation.',
    )
    text_model_name = models.CharField(
        max_length=100,
        default='claude-sonnet-4-6',
        help_text='Specific model name (e.g. "claude-sonnet-4-6", "gpt-4o").',
    )

    # ── Image Generation ────────────────────────────────────────────────────
    image_model_provider = models.CharField(
        max_length=20, choices=IMAGE_PROVIDER_CHOICES,
        default=PROVIDER_GOOGLE,
        help_text='AI provider for image generation.',
    )
    image_model_name = models.CharField(
        max_length=100,
        default='gemini-2.0-flash-exp',
        help_text='Specific image model name.',
    )

    # ── Fallback ────────────────────────────────────────────────────────────
    fallback_text_model = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Fallback model if the primary text model fails.',
    )

    # ── Limits ──────────────────────────────────────────────────────────────
    max_tokens_per_generation = models.IntegerField(
        default=8000,
        help_text='Maximum tokens per AI generation call.',
    )

    # ── Async Toggle ────────────────────────────────────────────────────────
    enable_async_generation = models.BooleanField(
        default=True,
        help_text='If True, long AI generation runs via Celery (if configured).',
    )

    # ── Timestamps ──────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Module Settings'
        verbose_name_plural = 'Module Settings'

    def __str__(self):
        return f'Proposal Settings — {self.organisation.name}'
