"""
AI Text Generation Service — Anthropic Claude integration.

Handles:
- Dynamic intake question generation (wizard Step 4)
- Full document generation from wizard answers
- Per-section text regeneration

All calls are wrapped in try/except, logged to AIJob, and read
API keys / model names from proposals/config.py.
"""
import time
import json
import logging
from proposals.config import get_config

logger = logging.getLogger(__name__)


def _get_anthropic_client():
    """Create and return an Anthropic client instance."""
    api_key = get_config('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError(
            'ANTHROPIC_API_KEY is not configured. '
            'Add it to your .env file or Django settings.'
        )
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        raise ImportError(
            'The anthropic package is not installed. '
            'Run: pip install anthropic>=0.25.0'
        )


def generate_intake_questions(doc_type, recipient_context=''):
    """
    Generate dynamic intake questions based on document type.

    Returns a list of question strings tailored to the document type.
    Falls back to default questions if AI is unavailable.
    """
    client = _get_anthropic_client()
    model = get_config('DEFAULT_TEXT_MODEL')

    system_prompt = (
        'You are a proposal writing assistant. Generate a list of 5-8 specific, '
        'clarifying questions that will help create an excellent document. '
        'Return ONLY a JSON array of question strings, nothing else. '
        'The questions should be tailored to the document type and context provided.'
    )

    user_prompt = (
        f'Document type: {doc_type}\n'
        f'Recipient context: {recipient_context or "Not specified"}\n\n'
        f'Generate intake questions for creating this type of document.'
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1000,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
        content = response.content[0].text.strip()
        # Parse JSON array from response
        questions = json.loads(content)
        if isinstance(questions, list):
            return questions
    except Exception as e:
        logger.warning(f'AI question generation failed: {e}')

    # Fallback
    return _default_questions(doc_type)


OUTLINE_SYSTEM_PROMPT = (
    "You are a senior proposal architect. Your job is to plan the structure of a "
    "{doc_type} document before it is written section by section.\n\n"
    "Return ONLY a valid JSON array. Each element must have these exact keys:\n"
    '- "order": integer (0-indexed)\n'
    '- "title": string (section heading)\n'
    '- "type": one of COVER, EXECUTIVE_SUMMARY, SECTION, TABLE, PRICING, TIMELINE, APPENDIX\n'
    '- "target_words": integer (how many words this section should contain)\n'
    '- "writing_instructions": string (1-2 sentences of specific guidance for the writer)\n\n'
    "Rules:\n"
    "1. Plan exactly enough sections to fill {target_pages} pages "
    "   (assume 500 words per page).\n"
    "2. No section should exceed {max_words_per_section} words.\n"
    "3. If a topic needs more words, split it into Part 1 / Part 2 sections.\n"
    "4. Always start with a COVER section and end with a Next Steps or Terms section.\n"
    "5. Return ONLY the JSON array. No markdown fences, no commentary.\n"
    "{extra_rules}"
)

def _build_outline_user_prompt(document, target_pages):
    parts = [
        f"Document type: {document.get_doc_type_display()}",
        f"Title: {document.title}",
        f"Recipient: {document.recipient_name or 'Not specified'}",
        f"Context: {document.recipient_context or 'Not specified'}",
        f"Target length: {target_pages} pages",
        "",
        "Intake answers:",
    ]
    for key, value in (document.wizard_answers or {}).items():
        clean_key = key.replace('question_', 'Q').replace('_', ' ')
        parts.append(f"- {clean_key}: {value}")
    return "\n".join(parts)

def _plan_document_outline(document, target_pages=20):
    client = _get_anthropic_client()
    model = get_config('DEFAULT_TEXT_MODEL')
    tokens_per_section = get_config('PROPOSALS_TOKENS_PER_SECTION')
    max_words = int(tokens_per_section * 0.75)
    max_sections = get_config('PROPOSALS_MAX_SECTIONS')

    extra_rules = ""
    if document.doc_type == 'FLYER':
        extra_rules += """
6.  Plan exactly 5–6 elements only: Headline, Subheadline, Benefits, 
    Supporting Detail, CTA, Contact.
7.  target_words per element: Headline=10, Subheadline=25, Benefits=80, 
    Supporting Detail=100, CTA=20, Contact=20.
8.  No single element should exceed 100 words. 
    Total document must not exceed 300 words.
9.  First element must identify the layout template choice using the 
    writing_instructions field, e.g. "Use HERO_SPLIT layout".
10. Always end with a CTA element.
11. Return ONLY the JSON array.
"""
    if document.doc_type == 'REPORT':
        extra_rules += "6. Make sure to specify graph inclusions in 'writing_instructions'.\n"
    if document.doc_type == 'CUSTOM' and document.wizard_answers and 'custom_prompt' in document.wizard_answers:
        extra_rules += f"7. Follow user custom prompt for section planning:\n{document.wizard_answers['custom_prompt']}\n"

    system = OUTLINE_SYSTEM_PROMPT.format(
        doc_type=document.get_doc_type_display(),
        target_pages=target_pages,
        max_words_per_section=max_words,
        extra_rules=extra_rules,
    )
    user = _build_outline_user_prompt(document, target_pages)

    response = client.messages.create(
        model=model,
        max_tokens=1500,   # outline is small — 1500 tokens is ample
        system=system,
        messages=[{'role': 'user', 'content': user}],
    )

    raw = response.content[0].text.strip()

    # Strip accidental markdown fences
    if raw.startswith('```'):
        parts = raw.split('```')
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith('json'):
            raw = raw[4:]

    outline = json.loads(raw)   # raises json.JSONDecodeError on bad output

    if not isinstance(outline, list) or not outline:
        raise ValueError(f"Outline response was not a non-empty list: {raw[:200]}")

    # Normalise: ensure required keys exist with safe defaults
    for i, section in enumerate(outline):
        section.setdefault('order', i)
        section.setdefault('type', 'SECTION')
        section.setdefault('target_words', 500)
        section.setdefault('writing_instructions', '')

    # Hard cap on section count
    if len(outline) > max_sections:
        logger.warning(
            f"Outline for doc {document.pk} has {len(outline)} sections, "
            f"truncating to {max_sections}"
        )
        outline = outline[:max_sections]

    logger.info(f"Outline generated for doc {document.pk}: {len(outline)} sections")
    return outline

def _generate_section(client, model, document, section_def, section_index, total_sections):
    """
    Generate HTML content for a single document section.

    Returns:
        tuple: (html_string, usage_object)
    """
    tokens_per_section = get_config('PROPOSALS_TOKENS_PER_SECTION')

    system_prompt = (
        f"You are writing section {section_index + 1} of {total_sections} "
        f"in a {document.get_doc_type_display()} for "
        f"{document.recipient_name or 'the client'}.\n\n"
        f"RULES:\n"
        f"1. Write ONLY the body content for this section. "
        f"   Do NOT include the section title as an <h1>.\n"
        f"2. Use semantic HTML: <h2>, <h3>, <p>, <ul>, <ol>, <table>, <strong>, <em>.\n"
        f"3. Target approximately {section_def['target_words']} words.\n"
        f"4. Do NOT add preamble, meta-commentary, or section markers.\n"
        f"5. Writing guidance: {section_def.get('writing_instructions', '')}\n"
    )

    user_prompt = (
        f"Section title: {section_def['title']}\n"
        f"Section type: {section_def['type']}\n\n"
        f"Document context:\n"
        f"- Title: {document.title}\n"
        f"- Recipient: {document.recipient_name or 'Not specified'}\n"
        f"- Context: {document.recipient_context or 'Not specified'}\n\n"
        f"Write the full content for this section now."
    )

    response = client.messages.create(
        model=model,
        max_tokens=tokens_per_section,
        system=system_prompt,
        messages=[{'role': 'user', 'content': user_prompt}],
    )

    return response.content[0].text, response.usage

def _enforce_target_pages(document, requested_pages, generation_type='simple') -> int:
    parsed_pages = requested_pages
    if not parsed_pages:
        answers = document.wizard_answers or {}
        for key in ('page_count', 'document_length', 'pages', 'length', 'question_page_count', 'question_pages', 'question_document_length'):
            val = answers.get(key)
            if val:
                try:
                    parsed_pages = int(str(val).split()[0])
                    break
                except (ValueError, TypeError):
                    pass
                    
    doc_type = document.doc_type
    if doc_type == 'FLYER':
        return 2
    elif doc_type in ('BROCHURE', 'DATASHEET'):
        return min(parsed_pages or 5, 5)
    elif doc_type in ('PROPOSAL', 'REPORT'):
        if generation_type == 'simple':
            return min(parsed_pages or 10, 10)
        else:
            return max(11, min(parsed_pages or 30, 50))
            
    return max(5, min(parsed_pages or 15, 100))

def _default_outline(doc_type: str) -> list:
    """Return a hardcoded 7-section outline when the outline API call fails."""
    sections = [
        ('Cover', 'COVER', 200),
        ('Executive Summary', 'EXECUTIVE_SUMMARY', 400),
        ('About Us', 'SECTION', 500),
        ('Problem Statement', 'SECTION', 500),
        ('Proposed Solution', 'SECTION', 600),
        ('Pricing', 'PRICING', 400),
        ('Next Steps', 'SECTION', 300),
    ]
    return [
        {'order': i, 'title': t, 'type': s, 'target_words': w, 'writing_instructions': ''}
        for i, (t, s, w) in enumerate(sections)
    ]

def _generate_document_single_call(document, user_id, job=None, target_pages=None):
    """
    Legacy path: single Anthropic API call for the entire document.
    Used for small documents (< PROPOSALS_SECTION_SYNC_THRESHOLD sections)
    when Celery is not configured. Preserves the exact original behaviour.
    """
    from proposals.models import DocumentSection, AIJob
    start_time = time.time()
    client = _get_anthropic_client()
    model = get_config('DEFAULT_TEXT_MODEL')
    max_tokens = get_config('MAX_TOKENS_PER_GENERATION')
    
    if target_pages is None:
        target_pages = _enforce_target_pages(document, None, 'simple')
        
    system_prompt = _build_document_system_prompt(document, target_pages)
    user_prompt = _build_document_user_prompt(document)
    if job:
        job.status = AIJob.STATUS_RUNNING
        job.prompt_used = f'SYSTEM: {system_prompt}\n\nUSER: {user_prompt}'
        job.model_used = model
        job.save(update_fields=['status', 'prompt_used', 'model_used', 'updated_at'])
    
    try:
        response = client.messages.create(
            model=model, max_tokens=max_tokens, system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
        content = response.content[0].text
        duration = time.time() - start_time
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        
        # Generate and inject images if it is a FLYER
        if document.doc_type == 'FLYER':
            try:
                from proposals.services.ai_image import generate_image
                placeholders = extract_image_placeholders(content)
                if placeholders:
                    generated_images = []
                    for p in placeholders:
                        if p.get('gemini_prompt'):
                            try:
                                img_res = generate_image(p['gemini_prompt'])
                                if img_res and 'image_url' in img_res:
                                    generated_images.append({
                                        'placeholder_index': p['placeholder_index'],
                                        'image_url': img_res['image_url'],
                                        'position': p['position'],
                                        'layout_zone': p['layout_zone']
                                    })
                            except Exception as e:
                                logger.error(f"Failed to generate flyer image: {e}")
                    
                    if generated_images:
                        content = replace_image_placeholders(content, generated_images)
            except Exception as e:
                logger.error(f"Image placeholder replacement failed: {e}")

        sections = _parse_document_sections(content, document.doc_type)
        for idx, section_data in enumerate(sections):
            DocumentSection.objects.create(
                document=document, order=idx,
                section_type=section_data.get('type', DocumentSection.TYPE_SECTION),
                title=section_data.get('title', ''),
                content_html=section_data.get('content', ''),
                content_raw=section_data.get('content', ''),
                ai_generated=True,
            )
        document.status = document.STATUS_DRAFT
        document.word_count = len(content.split())
        document.generated_html = content
        document.save(update_fields=['status', 'word_count', 'generated_html', 'updated_at'])
        if job:
            job.status = AIJob.STATUS_COMPLETE
            job.tokens_used = tokens_used
            job.duration_seconds = duration
            job.result_data = {'sections_created': len(sections)}
            job.save(update_fields=['status', 'tokens_used', 'duration_seconds', 'result_data', 'updated_at'])
    except Exception as e:
        logger.exception(f'Document generation failed: {e}')
        duration = time.time() - start_time
        document.status = document.STATUS_DRAFT
        document.save(update_fields=['status', 'updated_at'])

        if job:
            job.status = AIJob.STATUS_FAILED
            job.error_message = str(e)
            job.duration_seconds = duration
            job.save(update_fields=['status', 'error_message', 'duration_seconds', 'updated_at'])
        raise

def generate_document_sync(document, user_id, job=None, target_pages=None, generation_type='simple'):
    """
    Generate a full document section by section.

    For small documents (sections <= PROPOSALS_SECTION_SYNC_THRESHOLD) with
    Celery disabled, falls back to the legacy single-call path automatically.
    """
    from proposals.models import DocumentSection, AIJob

    # Enforce page limit based on doc type constraints
    target_pages = _enforce_target_pages(document, target_pages, generation_type)

    # If simple generation is requested, use the single call legacy path
    if generation_type == 'simple':
        return _generate_document_single_call(document, user_id, job=job, target_pages=target_pages)

    start_time = time.time()
    client = _get_anthropic_client()
    model = get_config('DEFAULT_TEXT_MODEL')
    sync_threshold = get_config('PROPOSALS_SECTION_SYNC_THRESHOLD')

    # Determine target pages from document or caller
    # (Already enforced above into target_pages)

    # --- Outline Phase ---
    if job:
        job.status = AIJob.STATUS_RUNNING
        job.model_used = model
        job.result_data = {
            'phase': 'outline',
            'sections_complete': 0,
            'sections_total': 0,
        }
        job.save(update_fields=['status', 'model_used', 'result_data', 'updated_at'])

    try:
        outline = _plan_document_outline(document, target_pages=target_pages)
    except Exception as e:
        logger.warning(f"Outline generation failed ({e}), using default outline")
        outline = _default_outline(document.doc_type)

    total_sections = len(outline)

    # Use legacy single-call path for small documents when Celery is off
    celery_enabled = get_config('ENABLE_CELERY')
    if not celery_enabled and total_sections <= sync_threshold:
        logger.info(
            f"Document {document.pk}: {total_sections} sections <= threshold "
            f"{sync_threshold}, using legacy single-call path"
        )
        return _generate_document_single_call(document, user_id, job=job, target_pages=target_pages)

    # --- Per-Section Loop ---
    if job:
        job.result_data = {
            'phase': 'generating',
            'sections_complete': 0,
            'sections_total': total_sections,
            'outline': outline,
            'current_section_title': outline[0]['title'] if outline else '',
        }
        job.save(update_fields=['result_data', 'updated_at'])

    total_tokens = 0
    sections_created = []

    # Fetch already-existing section orders (for retry safety)
    existing_orders = set(document.sections.values_list('order', flat=True))

    for idx, section_def in enumerate(outline):
        section_title = section_def['title']

        # Skip sections already created (retry safety)
        if idx in existing_orders:
            logger.info(f"Section {idx} '{section_title}' already exists, skipping")
            if job:
                job.result_data['sections_complete'] = idx + 1
                job.save(update_fields=['result_data', 'updated_at'])
            continue

        # Update progress before each section
        if job:
            job.result_data['current_section_title'] = section_title
            job.result_data['sections_complete'] = idx
            job.save(update_fields=['result_data', 'updated_at'])

        # Generate with per-section retry on rate limits
        content_html = None
        section_tokens = 0
        for attempt in range(3):
            try:
                content_html, usage = _generate_section(
                    client=client,
                    model=model,
                    document=document,
                    section_def=section_def,
                    section_index=idx,
                    total_sections=total_sections,
                )
                section_tokens = usage.input_tokens + usage.output_tokens
                break
            except Exception as e:
                import anthropic as _anthropic
                if hasattr(_anthropic, 'RateLimitError') and isinstance(e, _anthropic.RateLimitError):
                    if attempt < 2:
                        logger.warning(f"Rate limit on section {idx}, sleeping 60s (attempt {attempt+1})")
                        time.sleep(60)
                        continue
                elif hasattr(_anthropic, 'AuthenticationError') and isinstance(e, _anthropic.AuthenticationError):
                    logger.error(f"Anthropic API key invalid for doc {document.pk}: {e}")
                    if job:
                        job.status = AIJob.STATUS_FAILED
                        job.error_message = f"API key invalid: {e}"
                        job.save(update_fields=['status', 'error_message', 'updated_at'])
                    raise
                logger.error(f"Section {idx} '{section_title}' failed for doc {document.pk}: {e}")
                content_html = (
                    f'<p class="text-danger">'
                    f'[Generation failed for this section: {e}. '
                    f'Click Regenerate to retry.]'
                    f'</p>'
                )
                break

        total_tokens += section_tokens

        section = DocumentSection.objects.create(
            document=document,
            order=idx,
            section_type=section_def.get('type', DocumentSection.TYPE_SECTION),
            title=section_title,
            content_html=content_html,
            content_raw=content_html,
            ai_generated=True,
        )
        sections_created.append(section.pk)

    # --- Finalise ---
    duration = time.time() - start_time
    document.status = document.STATUS_DRAFT
    document.word_count = sum(
        len((s.content_raw or '').split())
        for s in DocumentSection.objects.filter(pk__in=sections_created)
    )
    document.save(update_fields=['status', 'word_count', 'updated_at'])

    if job:
        job.status = AIJob.STATUS_COMPLETE
        job.tokens_used = total_tokens
        job.duration_seconds = duration
        job.result_data = {
            'phase': 'complete',
            'sections_complete': total_sections,
            'sections_total': total_sections,
            'sections_created': sections_created,
        }
        job.save(update_fields=[
            'status', 'tokens_used', 'duration_seconds', 'result_data', 'updated_at'
        ])

def regenerate_section_sync(section, user_id, job=None):
    """Regenerate a single section's content via AI."""
    from proposals.models import AIJob

    start_time = time.time()

    try:
        client = _get_anthropic_client()
        model = get_config('DEFAULT_TEXT_MODEL')

        system_prompt = (
            f'You are rewriting a section of a {section.document.get_doc_type_display()}. '
            f'Maintain the same style and tone. Return only the HTML content for this section.'
        )
        user_prompt = (
            f'Section type: {section.get_section_type_display()}\n'
            f'Section title: {section.title}\n'
            f'Current content to improve:\n{section.content_raw or section.content_html}\n\n'
            f'Rewrite this section to be more compelling and professional.'
        )

        if job:
            job.status = AIJob.STATUS_RUNNING
            job.prompt_used = f'SYSTEM: {system_prompt}\n\nUSER: {user_prompt}'
            job.model_used = model
            job.save(update_fields=['status', 'prompt_used', 'model_used', 'updated_at'])

        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
        )

        content = response.content[0].text
        duration = time.time() - start_time
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        section.content_html = content
        section.ai_generated = True
        section.save(update_fields=['content_html', 'ai_generated', 'updated_at'])

        if job:
            job.status = AIJob.STATUS_COMPLETE
            job.tokens_used = tokens_used
            job.duration_seconds = duration
            job.save(update_fields=['status', 'tokens_used', 'duration_seconds', 'updated_at'])

    except Exception as e:
        logger.exception(f'Section regeneration failed: {e}')
        if job:
            job.status = AIJob.STATUS_FAILED
            job.error_message = str(e)
            job.save(update_fields=['status', 'error_message', 'updated_at'])
        raise


def _build_document_system_prompt(document, target_pages=None):
    """Build the system prompt for full document generation based on doc_type."""
    brand_info = ''
    if document.brand_guideline:
        bg = document.brand_guideline
        brand_info = (
            f'\nBrand guidelines to follow:\n'
            f'- Primary color: {bg.primary_color}\n'
            f'- Secondary color: {bg.secondary_color}\n'
            f'- Heading font: {bg.heading_font}\n'
            f'- Body font: {bg.body_font}\n'
        )

    doc_type = document.doc_type

    custom_prompt_instructions = ""
    if doc_type == 'CUSTOM' and document.wizard_answers and 'custom_prompt' in document.wizard_answers:
        custom_prompt_instructions = document.wizard_answers['custom_prompt']

    target_pages_instruction = ""
    if target_pages:
        target_pages_instruction = f" You must structure the document to fill approximately {target_pages} pages."

    if doc_type == 'FLYER':
        return f"""You are an expert marketing designer AND copywriter creating a visually stunning 
promotional flyer (1–2 pages). You are responsible for both the CONTENT and the 
VISUAL LAYOUT STRUCTURE.

═══════════════════════════════════════
STEP 1 — CHOOSE A LAYOUT TEMPLATE
═══════════════════════════════════════
Select the most appropriate layout from the options below based on the industry, 
tone, and content provided. Output your choice as:
<!-- LAYOUT: [template_name] -->

Available layouts:
- HERO_SPLIT      → Large image left or right, bold headline + bullets opposite.
                    Best for: tech, software, B2B services.
- HERO_FULL       → Full-bleed background image, text overlaid with contrast block.
                    Best for: events, launches, luxury, real estate.
- GRID_MULTI      → 2–3 product/service images in a grid, minimal text alongside.
                    Best for: products, retail, e-commerce, gifting.
- DIAGONAL_BAND   → Diagonal colour band splits the page, image top-right,
                    text bottom-left. Best for: corporate, finance, consulting.
- ICON_GRID       → No hero image, uses icon + short text blocks in a grid.
                    Best for: service lists, feature comparisons, SaaS.
- MINIMAL_CENTER  → Centered layout, lots of white space, one strong image.
                    Best for: luxury, wellness, beauty, premium brands.
- TECH_HEXAGON    → Diagonal split with hexagon-shaped image wrappers.
                    Best for: IT services, software integrations, cybersecurity.
- CORPORATE_CURVES→ Soft curved backgrounds with a floating device (tablet/phone) image.
                    Best for: Professional services, SaaS platforms, tech solutions.
- PRODUCT_GRID    → Top hero banner with a product grid (4 columns) below.
                    Best for: Retail sales, grocery, e-commerce promotions.

═══════════════════════════════════════
STEP 2 — WRITE THE CONTENT
═══════════════════════════════════════
Follow these rules:

TYPOGRAPHY HIERARCHY (mandatory):
- <h1 class="flyer-headline">    → Main headline. MAX 6 words. Bold, commanding.
- <h2 class="flyer-subheadline"> → Subheadline. MAX 12 words. Benefit-driven.
- <p class="flyer-body">         → Body copy. MAX 2 sentences. Only if needed.
- <ul class="flyer-bullets">     → 3–5 benefits. MAX 8 words each.
- <p class="flyer-cta">          → Single CTA. Action verb. ("Book a Free Demo")
- <p class="flyer-contact">      → Contact line. Phone / Website / Email.

TEMPLATE-SPECIFIC HTML STRUCTURES:
- For TECH_HEXAGON, wrap images in `<div class="hexagon-wrapper">` inside `<div class="image-zone">`. Content goes in `<div class="content-zone">`.
- For CORPORATE_CURVES, place the main image inside `<div class="floating-device">`. Content goes in `<div class="content-zone">`.
- For PRODUCT_GRID, create a `<div class="hero-banner">` (with `<div class="hero-content">` and `<div class="hero-image-wrapper">`) followed by a `<div class="grid-container">`. Inside the grid, use `<div class="product-card">` with an image placeholder, `<h3 class="product-title">`, and `<p class="product-price">`.

DESIGN ELEMENTS:
- Include 1 decorative element hint using:
  <div class="design-element" data-shape="[hexagon|diagonal|circle|band]" 
       data-colour="[primary|accent|dark]"></div>
- This tells the renderer to add geometric accents matching the brand.

CONTENT RULES:
- Total word count: MAX 120 words across the entire flyer.
- Every word must earn its place. Cut ruthlessly.
- Tone must match industry:
    Tech/B2B       → Bold, confident, outcome-focused
    Retail/Gifting → Warm, aspirational, sensory
    Finance/Legal  → Authoritative, precise, trustworthy
    Health/Wellness→ Calm, reassuring, benefit-led

═══════════════════════════════════════
STEP 3 — WRITE GEMINI IMAGE PROMPTS
═══════════════════════════════════════
Include image placeholders with detailed Gemini generation prompts.

For HERO_SPLIT / DIAGONAL_BAND / HERO_FULL layouts — 1 hero image:
<div class="image-placeholder"
     data-gemini-prompt="[Highly specific prompt including:
       1. Visual style (photorealistic / flat illustration / 3D render / cinematic)
       2. Subject (what is shown exactly)
       3. Mood and lighting (dramatic / clean / warm / corporate)
       4. Colour palette (must complement brand colours if provided)
       5. Composition (close-up / wide / overhead / dynamic angle)
       6. Background (pure white / blurred office / abstract tech pattern)
       7. What to AVOID (text in image / cluttered background / stock-photo feel)]"
     data-position="hero"
     data-aspect-ratio="[1:1|4:3|16:9|2:3]"
     data-layout-zone="[left|right|top|background]">
[Image: brief description]
</div>

For GRID_MULTI layouts — generate 2 to 3 separate image-placeholder divs, 
varying angle, lighting, and composition across each one:
- Image 1: front-facing, clean studio lighting
- Image 2: lifestyle or in-context usage shot
- Image 3: detail or close-up shot

═══════════════════════════════════════
STEP 4 — OUTPUT STRUCTURE
═══════════════════════════════════════
Output in this exact order:
1. <!-- LAYOUT: template_name -->
2. <div class="flyer-wrapper flyer--[template_name_lowercase]">
3.   Image placeholder(s) — hero image first if HERO_SPLIT or HERO_FULL layout
4.   Text content using correct CSS classes
5.   Design element hints
6.   CTA and contact
7. </div>

Do NOT include: preamble, meta-commentary, section markers (<!-- SECTION -->),
pricing tables, methodology, or any text outside the flyer-wrapper div.

{custom_prompt_instructions}
{brand_info}
"""

    if doc_type == 'BROCHURE':
        return f"""You are an expert marketing copywriter writing copy for a MULTI-PANEL brochure 
(tri-fold or bi-fold format, 4–6 panels across up to 5 pages).

CRITICAL RULES:
1. Structure content as distinct, self-contained panels — each panel must be 
   independently scannable.
2. Typical panel order: Front Cover → Problem or Hook → Solution Overview → 
   Key Features or Benefits → Social Proof or Case Study → Back Cover with CTA.
3. Each panel uses: one <h2> heading, 2–4 short <p> tags OR a <ul> with 3–5 items. 
   Never exceed 100 words per panel.
4. Use <!-- SECTION: PanelName --> to separate every panel.
5. Language must be benefit-driven, visually engaging, and emotionally resonant. 
   Avoid jargon and long sentences.
6. IMAGE RULE — Every panel MUST have an image placeholder using this exact format:
   <div class="image-placeholder"
        data-gemini-prompt="[detailed image generation prompt for Gemini: style, subject, mood, colours, composition]"
        data-position="[hero|inline|sidebar]"
        data-aspect-ratio="[16:9|1:1|4:3|2:3]">
   [Image: brief human-readable description]
   </div>
   The Cover panel must have a hero/full-bleed image prompt. 
   Other panels should have supporting inline or sidebar images.
   Each data-gemini-prompt must be unique and specific to that panel's content and mood.
7. Do NOT write like a proposal. No methodology, no terms, no pricing tables.
8. Tone: warm, persuasive, and brand-forward.
9. Do NOT include preamble or meta-commentary outside the brochure content.

{brand_info}
"""

    if doc_type == 'DATASHEET':
        return f"""You are a technical writer creating a PRODUCT DATASHEET — a structured 1–2 page 
reference document for a technical or business audience.

CRITICAL RULES:
1. Mandatory structure (in this exact order): Product Title → Tagline → Overview → 
   Key Features → Technical Specifications → Use Cases → Why Choose Us → Contact / CTA.
2. Use <table> with <th> and <td> for Technical Specifications — non-negotiable. 
   Use "[specify]" as placeholder for unknown values.
3. Use <ul> with <li> for all feature and use-case lists. Max 15 words per item.
4. Overview section must be max 60 words.
5. Tone: precise, factual, confident. No superlatives in specification sections.
6. Use <!-- SECTION: SectionName --> to separate every section.
7. Do NOT pad content. Every sentence must carry information value.
8. IMAGE RULE — Include exactly 2 image placeholders:
   - One after the Overview section (product hero image or diagram):
     <div class="image-placeholder"
          data-gemini-prompt="[detailed image generation prompt: photorealistic/technical diagram, 
          product name, key visual features, clean white/neutral background, professional lighting, 
          style matching a B2B product datasheet]"
          data-position="hero"
          data-aspect-ratio="16:9">
     [Image: product hero or diagram]
     </div>
   - One in the Use Cases section (contextual usage image):
     <div class="image-placeholder"
          data-gemini-prompt="[detailed image generation prompt: real-world usage scenario, 
          professional setting, people or environment using the product/service, 
          mood and colour tone matching the brand]"
          data-position="inline"
          data-aspect-ratio="4:3">
     [Image: use case scenario]
     </div>
9. Do NOT include narrative prose or proposal-style sections.

{brand_info}
"""

    if doc_type == 'CUSTOM':
        return f"""You are an expert document writer producing a CUSTOM document as specified below.

CRITICAL RULES:
1. The user's custom instructions define type, tone, structure, and purpose — 
   follow them precisely above all defaults.
2. If structure is not specified, default to: Cover / Introduction / 
   Main Content Sections / Summary / Call to Action.
3. Use semantic HTML: <h1>, <h2>, <h3>, <p>, <ul>, <ol>, <table>, <strong>, <em>.
4. Use <!-- SECTION: SectionTitle --> to separate every section.
5. IMAGE RULE — If the document type would benefit from images (e.g. marketing, 
   visual, or presentation documents), include image placeholders using this format:
   <div class="image-placeholder"
        data-gemini-prompt="[detailed image generation prompt: style, subject, mood, 
        colours, composition — be as specific as possible for best Gemini output]"
        data-position="[hero|inline|sidebar|background]"
        data-aspect-ratio="[16:9|1:1|4:3|2:3]">
   [Image: brief human-readable description]
   </div>
   If the document is purely text-based (e.g. legal, technical spec, internal memo), 
   omit image placeholders entirely.
6. Match the tone in the user's instructions. Default to professional if unspecified.
7. Do NOT force a proposal structure. Let the custom instructions define the shape.
8. Do NOT include preamble or meta-commentary outside the document content.

CUSTOM USER INSTRUCTIONS:
{custom_prompt_instructions}

{brand_info}
"""

    # Default for PROPOSAL and REPORT
    doc_type_display = document.get_doc_type_display().lower()
    report_instructions = ""
    if doc_type == 'REPORT':
        report_instructions = """
7. This is a structured business Report. Follow this section order strictly:
   Executive Summary → Background / Context → Methodology → Key Findings → 
   Analysis → Recommendations → Conclusion → Appendix (if needed).
8. Executive Summary must be self-contained and max 200 words.
9. CHART RULE — For every section discussing quantitative or comparative data, 
   include a chart placeholder using this exact format:
   <div class="chart-placeholder"
        data-type="[bar|line|pie|donut|scatter]"
        data-title="[Exact chart title]"
        data-x-label="[X axis label if applicable]"
        data-y-label="[Y axis label if applicable]"
        data-description="[What data this chart shows and why it matters]">
   [Chart: human-readable description]
   </div>
   Charts are rendered programmatically — do NOT use Gemini for charts.
10. IMAGE RULE — For non-chart visuals (e.g. process diagrams, team photos, 
    infographic elements), use this format for Gemini:
    <div class="image-placeholder"
         data-gemini-prompt="[detailed image generation prompt: style, subject, 
         professional business context, colour palette, composition]"
         data-position="[inline|full-width]"
         data-aspect-ratio="[16:9|4:3]">
    [Image: brief description]
    </div>
11. Use <table> for comparative or multi-variable data.
12. Recommendations must be a numbered <ol>. Each must start with an action verb 
    (Implement, Reduce, Invest, Launch, etc.).
"""

    return (
        f'You are an expert {doc_type_display} writer producing a COMPLETE, FULL-LENGTH document.{target_pages_instruction}\n\n'
        f'CRITICAL RULES — you MUST follow all of these:\n'
        f'1. Generate the ENTIRE document from start to finish. Do NOT stop early, do NOT summarise, '
        f'do NOT write placeholder text like "[continue...]" or "[rest of section]".\n'
        f'2. A full {doc_type_display} must have AT LEAST 7 sections. Typical sections: '
        f'Cover / Executive Summary / About Us / Problem Statement / Proposed Solution / '
        f'Methodology / Timeline / Pricing / Team / Next Steps / Terms & Conditions.\n'
        f'3. Each section must contain substantial, detailed content — minimum 3 paragraphs or '
        f'equivalent structured content (tables, bullet lists, etc.).\n'
        f'4. Use semantic HTML tags (<h1>, <h2>, <h3>, <p>, <ul>, <ol>, <table>, <strong>, <em>).\n'
        f'5. Separate every section with a marker on its own line: <!-- SECTION: SectionTitle -->\n'
        f'6. Do NOT include any preamble, meta-commentary, or closing remarks outside the document content.\n'
        f'{report_instructions}'
        f'{brand_info}\n'
        f'Make the content compelling, professional, specific, and tailored to the recipient. '
        f'Use concrete details, not generic filler text.'
    )


def _build_document_user_prompt(document):
    """Build the user prompt from wizard data."""
    parts = [
        f'Document type: {document.get_doc_type_display()}',
        f'Title: {document.title}',
    ]

    if document.recipient_name:
        parts.append(f'Recipient: {document.recipient_name}')
    if document.recipient_context:
        parts.append(f'Context: {document.recipient_context}')

    if document.wizard_answers:
        parts.append('\nIntake answers:')
        for key, value in document.wizard_answers.items():
            clean_key = key.replace('question_', 'Q').replace('_', ' ')
            parts.append(f'- {clean_key}: {value}')

    # Include reference document text if available
    ref_assets = document.assets.filter(
        asset_type='REFERENCE_DOC',
        extracted_text__gt='',
    )
    if ref_assets:
        parts.append('\nReference material:')
        for asset in ref_assets[:3]:  # Limit to 3 to avoid token overflow
            parts.append(f'--- {asset.original_filename} ---')
            parts.append(asset.extracted_text[:2000])  # Truncate long docs

    return '\n'.join(parts)


def _parse_document_sections(content, doc_type):
    """Parse AI-generated content into section dicts."""
    import re
    sections = []

    # Try to split by section markers
    parts = re.split(r'<!--\s*SECTION:\s*(.+?)\s*-->', content)

    if len(parts) > 1:
        # First part is before any section marker (might be empty)
        if parts[0].strip():
            sections.append({
                'type': 'COVER',
                'title': 'Cover',
                'content': parts[0].strip(),
            })
        # Remaining parts alternate: title, content, title, content, ...
        for i in range(1, len(parts), 2):
            title = parts[i].strip()
            content_block = parts[i + 1].strip() if i + 1 < len(parts) else ''
            section_type = _infer_section_type(title)
            sections.append({
                'type': section_type,
                'title': title,
                'content': content_block,
            })
    else:
        # No section markers — treat entire content as one section
        sections.append({
            'type': 'SECTION',
            'title': 'Document Content',
            'content': content.strip(),
        })

    return sections


def _infer_section_type(title):
    """Infer section type from title text."""
    title_lower = title.lower()
    if 'cover' in title_lower:
        return 'COVER'
    elif 'executive' in title_lower or 'summary' in title_lower:
        return 'EXECUTIVE_SUMMARY'
    elif 'pricing' in title_lower or 'cost' in title_lower or 'budget' in title_lower:
        return 'PRICING'
    elif 'timeline' in title_lower or 'schedule' in title_lower:
        return 'TIMELINE'
    elif 'appendix' in title_lower or 'appendices' in title_lower:
        return 'APPENDIX'
    elif 'table' in title_lower:
        return 'TABLE'
    return 'SECTION'


def _default_questions(doc_type):
    """Return default questions when AI is not available."""
    return [
        'Who is the target audience for this document?',
        'What is the main objective or goal?',
        'What key points should be highlighted?',
        'What tone should the document have (formal, conversational, technical)?',
        'Are there any specific requirements or constraints?',
    ]

def extract_image_placeholders(html_content: str) -> list[dict]:
    """
    Parses Sonnet-generated HTML and extracts all image placeholder metadata
    so they can be sent to the Gemini image generation pipeline.
    
    Returns a list of dicts with keys:
    - gemini_prompt: str    (the prompt to send to Gemini)
    - position: str         (hero / inline / sidebar / background)
    - aspect_ratio: str     (16:9 / 1:1 / 4:3 / 2:3)
    - layout_zone: str      (left / right / top / background)
    - placeholder_index: int (order in document, 0-indexed)
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, "html.parser")
    placeholders = soup.find_all("div", class_="image-placeholder")
    results = []
    
    for index, placeholder in enumerate(placeholders):
        results.append({
            "gemini_prompt":     placeholder.get("data-gemini-prompt", ""),
            "position":          placeholder.get("data-position", "inline"),
            "aspect_ratio":      placeholder.get("data-aspect-ratio", "16:9"),
            "layout_zone":       placeholder.get("data-layout-zone", ""),
            "placeholder_index": index,
        })
    
    return results

def replace_image_placeholders(html_content: str, 
                                generated_images: list[dict]) -> str:
    """
    Replaces image-placeholder divs with actual <img> tags after 
    Gemini has generated the images.
    
    generated_images: list of dicts with keys:
    - placeholder_index: int
    - image_url: str
    - position: str
    - layout_zone: str
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, "html.parser")
    placeholders = soup.find_all("div", class_="image-placeholder")
    
    image_map = {img["placeholder_index"]: img for img in generated_images}
    
    for index, placeholder in enumerate(placeholders):
        if index in image_map:
            img_data = image_map[index]
            img_tag = soup.new_tag(
                "img",
                src=img_data["image_url"],
                alt=placeholder.get_text(strip=True),
            )
            img_tag["class"] = [
                "flyer-image",
                f"flyer-image--{img_data.get('position', 'inline')}",
                f"flyer-image--zone-{img_data.get('layout_zone', 'default')}",
            ]
            placeholder.replace_with(img_tag)
    
    return str(soup)

def extract_flyer_layout(html_content: str) -> str:
    """
    Reads the <!-- LAYOUT: xxx --> comment written by Sonnet
    and returns the layout template name as a lowercase string.
    Falls back to 'hero_split' if not found.
    
    Example: <!-- LAYOUT: HERO_SPLIT --> returns 'hero_split'
    """
    import re
    match = re.search(r'<!--\s*LAYOUT:\s*(\w+)\s*-->', html_content, re.IGNORECASE)
    if match:
        return match.group(1).strip().lower()
    return 'hero_split'
