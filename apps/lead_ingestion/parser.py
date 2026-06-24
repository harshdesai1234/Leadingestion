import re
import json
import time
import logging
from urllib.parse import unquote
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

MAX_PAYLOAD_BYTES = 102_400  # 100 KB


class ParseError(Exception):
    """Raised when lead parsing fails."""
    pass


def clean_phone_number(phone: str) -> str:
    if not phone:
        return ""
    return re.sub(r'[\s\-\(\)]', '', phone)


def validate_phone(phone: str) -> bool:
    if not phone:
        return False
    cleaned = clean_phone_number(phone)
    return bool(re.match(r'^\+?\d{7,15}$', cleaned))


def parse_lead(payload: str, tenant_id: int = None, source_hint: str = '') -> dict:
    """
    Call the Anthropic Claude API to extract structured fields
    (name, phone, email, source) from a raw verbatim payload.

    Raises ParseError on API failure, invalid JSON response, or
    when both phone and email are missing.
    """
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY is not set. Using mock parsing mode.")
        return _mock_parse(payload, source_hint=source_hint)

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    truncated = payload[:MAX_PAYLOAD_BYTES] if len(payload.encode('utf-8')) > MAX_PAYLOAD_BYTES else payload

    prompt = (
        "You are a data-extraction engine for a sales platform.\n"
        "Extract exactly these fields from the lead data provided:\n"
        "  name, phone, email, source\n"
        "Rules:\n"
        "- Respond with ONLY a JSON object. No markdown, no explanation.\n"
        "- Use null for any field that is genuinely not present.\n"
        "- 'source' must be one of: linkedin, instagram, facebook, "
        "google_ads, youtube, website, other.\n"
        "- Normalise phone to international format with country code "
        "when the country is identifiable; otherwise keep digits as-is.\n"
        "Example output:\n"
        '{"name": "Priya Sharma", "phone": "+919812345621", '
        '"email": "priya@example.com", "source": "linkedin"}\n\n"'
        f"Raw Payload:\n{truncated}"
    )

    max_retries = 2
    delay = 1.0
    response = None

    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Sending request to Claude (attempt {attempt + 1}) for tenant {tenant_id}")
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1000,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
                timeout=30.0,
            )
            break
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Failed to reach Claude API after {max_retries} retries: {str(e)}")
                raise ParseError(f"Anthropic API error: {str(e)}")
            logger.warning(f"Claude API call failed (attempt {attempt + 1}): {str(e)}. Retrying in {delay}s...")
            time.sleep(delay)
            delay *= 2.0

    if not response or not response.content:
        raise ParseError("Received empty response from Anthropic Claude API.")

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    logger.info(f"Token usage for tenant {tenant_id}: Input={input_tokens}, Output={output_tokens}")

    raw_text = response.content[0].text.strip()

    if raw_text.startswith("```"):
        raw_text = re.sub(r'^```(?:json)?\n', '', raw_text)
        raw_text = re.sub(r'\n```$', '', raw_text)
        raw_text = raw_text.strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude output as JSON: {raw_text}")
        raise ParseError(f"Claude response is not valid JSON: {str(e)}")

    return validate_extracted_data(data, source_hint=source_hint)


def validate_extracted_data(data: dict, source_hint: str = '') -> dict:
    """
    Validate and normalize structured lead data extracted by the LLM.

    Raises ParseError if both phone and email are missing — the lead is not actionable.
    """
    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')
    source = data.get('source')
    confidence_note = data.get('confidence_note', '')

    if name in (None, "None", "null", ""):
        name = None
    if phone in (None, "None", "null", ""):
        phone = None
    if email in (None, "None", "null", ""):
        email = None

    if email:
        try:
            validate_email(email)
        except ValidationError:
            logger.warning(f"Extracted email '{email}' is invalid. Setting to None.")
            confidence_note = (confidence_note + " [email invalid]").strip()
            email = None

    if phone:
        cleaned_p = clean_phone_number(phone)
        if validate_phone(cleaned_p):
            phone = cleaned_p
        else:
            logger.warning(f"Extracted phone '{phone}' is invalid. Setting to None.")
            confidence_note = (confidence_note + " [phone invalid]").strip()
            phone = None

    if not phone and not email:
        raise ParseError(
            "Both phone and email are missing. This lead is not actionable."
        )

    allowed_sources = {'linkedin', 'instagram', 'facebook', 'google_ads', 'youtube', 'website', 'webhook', 'other'}
    if source not in allowed_sources and not (source and source.startswith('csv_upload')):
        if source_hint in allowed_sources or source_hint.startswith('csv_upload'):
            source = source_hint
        else:
            source = 'other'

    return {
        'name': name,
        'phone': phone,
        'email': email,
        'source': source,
        'confidence_note': confidence_note,
    }


def _mock_parse(payload: str, source_hint: str = '') -> dict:
    """Mock parser used when ANTHROPIC_API_KEY is not set."""
    decoded = unquote(payload)

    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', decoded)
    email = email_match.group(0) if email_match else None

    phone_match = re.search(r'\+?\d[\d\s\-\(\)]{6,14}\d', decoded)
    phone = phone_match.group(0) if phone_match else None

    name_match = re.search(r'(?:name|customer|full_name)[=:"\s]+([^&"\\,\}\n]+)', decoded, re.IGNORECASE)
    name = name_match.group(1).strip() if name_match else "Extracted Lead"

    source = None
    decoded_lower = decoded.lower()
    for s in ['linkedin', 'instagram', 'facebook', 'google_ads', 'website']:
        if s in decoded_lower or s.replace('_', ' ') in decoded_lower:
            source = s
            break

    data = {
        'name': name,
        'phone': phone,
        'email': email,
        'source': source,
        'confidence_note': 'Mock extracted',
    }
    return validate_extracted_data(data, source_hint=source_hint)
