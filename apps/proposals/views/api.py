"""
API views — internal HTMX/AJAX endpoints for the proposals module.

These endpoints handle AI question generation, job status polling,
image generation, and auto-save — all without full page reloads.
"""
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from proposals.permissions import proposal_permission_required
from proposals.models import Document, AIJob


@require_POST
@proposal_permission_required(action='create')
def generate_questions(request):
    """
    Generate dynamic intake questions based on document type.
    Called via HTMX from wizard Step 4.
    """
    doc_type = request.POST.get('doc_type', 'PROPOSAL')
    recipient_context = request.POST.get('recipient_context', '')

    try:
        from proposals.services.ai_text import generate_intake_questions
        questions = generate_intake_questions(doc_type, recipient_context)
        return JsonResponse({'questions': questions})
    except Exception as e:
        return JsonResponse({
            'questions': _get_fallback_questions(doc_type),
            'warning': f'AI unavailable, using default questions: {str(e)}',
        })


@proposal_permission_required(action='read')
def job_status(request, job_id):
    """Poll AI job status (called via HTMX or fetch)."""
    job = get_object_or_404(AIJob, pk=job_id)

    # Verify tenant access
    org = getattr(request, 'organization', None)
    if org and job.document.organisation != org:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    result = job.result_data or {}
    # Backward-compatible: old jobs used 'sections_created', new jobs use 'sections_complete'
    sections_complete = result.get('sections_complete', result.get('sections_created', 0))
    sections_total = result.get('sections_total', sections_complete or 1)
    percent = int(sections_complete / sections_total * 100) if sections_total > 0 else 0

    data = {
        'status': job.status,
        'is_complete': job.is_complete,
        'is_failed': job.is_failed,
        'error_message': job.error_message if job.is_failed else '',
        'phase': result.get('phase', 'pending'),
        'sections_complete': sections_complete,
        'sections_total': sections_total,
        'current_section_title': result.get('current_section_title', ''),
        'percent': percent,
    }
    return JsonResponse(data)


@require_POST
@proposal_permission_required(action='create')
def generate_image_api(request):
    """Generate an AI image from a text prompt or selection."""
    prompt = request.POST.get('prompt', '')
    doc_id = request.POST.get('document_id')
    section_id = request.POST.get('section_id')
    resolution = request.POST.get('resolution', '1K')

    if not prompt:
        return JsonResponse({'error': 'Prompt is required'}, status=400)

    try:
        from proposals.services.ai_image import generate_image
        result = generate_image(prompt, resolution=resolution)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@proposal_permission_required(action='update')
def autosave(request, doc_id):
    """Auto-save document metadata (called via HTMX)."""
    org = getattr(request, 'organization', None)
    document = get_object_or_404(Document, pk=doc_id, organisation=org)

    title = request.POST.get('title')
    if title:
        document.title = title

    status = request.POST.get('status')
    if status and status in dict(Document.STATUS_CHOICES):
        document.status = status

    document.save()
    return JsonResponse({'status': 'success', 'title': document.title, 'document_status': document.status})


def _get_fallback_questions(doc_type):
    """Return sensible default questions when AI is unavailable."""
    base_questions = [
        'Who is the recipient and what industry are they in?',
        'What problem are you solving for them?',
        'What are the key benefits of your solution?',
    ]

    type_questions = {
        'PROPOSAL': [
            'What is the project scope and timeline?',
            'What is the budget range?',
            'What are the expected deliverables?',
        ],
        'FLYER': [
            'What is the main call-to-action?',
            'What event or promotion is this for?',
        ],
        'BROCHURE': [
            'What products or services should be highlighted?',
            'Who is the target audience?',
        ],
        'DATASHEET': [
            'What technical specifications should be included?',
            'What are the key product features?',
        ],
        'REPORT': [
            'What time period does this report cover?',
            'What metrics or KPIs should be highlighted?',
        ],
    }

    return base_questions + type_questions.get(doc_type, [])
