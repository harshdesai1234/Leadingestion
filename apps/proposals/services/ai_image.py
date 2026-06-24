"""
AI Image Generation Service — Google Imagen 3 integration.

Handles contextual image generation for document sections
and text-selection-triggered image generation.

Uses Google's Imagen 3 model (imagen-3.0-generate-002) via the
google-generativeai SDK. Returns a base64 data URL so the image
can be embedded directly in the document without a separate upload step.
"""
import base64
import logging
from proposals.config import get_config

logger = logging.getLogger(__name__)

# Use Nano Banana 2 (gemini-3.1-flash-image-preview)
IMAGEN_MODEL = 'gemini-3.1-flash-image-preview'

def generate_image(prompt, style_hints=None, resolution='1K'):
    """
    Generate an image using Google Gemini Nano Banana 2.

    Args:
        prompt: Text description of the image to generate.
        style_hints: Optional dict with brand style hints (colours, etc.)
        resolution: Resolution of the image (0.5K, 1K, 2K, 4K).

    Returns:
        dict with 'image_url' key containing a base64 data URL (data:image/png;base64,...).
    """
    api_key = get_config('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError(
            'GOOGLE_API_KEY is not configured. '
            'Add it to your .env file or Django settings.'
        )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # Build enhanced prompt with style hints
        full_prompt = _build_image_prompt(prompt, style_hints)
        
        if resolution:
            full_prompt += f"\n\nResolution: {resolution}"

        response = client.models.generate_content(
            model=IMAGEN_MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            )
        )

        image_data = None
        for part in response.parts:
            if getattr(part, 'inline_data', None):
                image_data = part.inline_data.data
                break
        
        if not image_data:
            raise ValueError('Gemini returned no image data. Check your prompt or API quota.')

        # Convert the raw image bytes to a base64 data URL
        b64 = base64.b64encode(image_data).decode('utf-8')
        data_url = f'data:image/png;base64,{b64}'

        return {
            'status': 'success',
            'image_url': data_url,
            'prompt_used': full_prompt,
            'model': IMAGEN_MODEL,
        }

    except ImportError:
        raise ImportError(
            'The google-genai package is not installed. '
            'Run: pip install google-genai'
        )
    except Exception as e:
        logger.exception(f'Image generation failed: {e}')
        raise


def _build_image_prompt(prompt, style_hints=None):
    """Build an enhanced prompt with optional style hints."""
    parts = [
        'Professional, clean, high-quality image suitable for a business document.',
        f'Subject: {prompt}',
        'Style: modern, corporate, photorealistic or clean illustration.',
        'No text overlays. No watermarks.',
    ]

    if style_hints:
        if 'primary_color' in style_hints:
            parts.append(f'Accent colour: {style_hints["primary_color"]}')
        if 'style' in style_hints:
            parts.append(f'Visual style: {style_hints["style"]}')

    return ' '.join(parts)
