"""
Editor views — Word-style document editor with section management.

Provides the main editor view, per-section auto-save, section regeneration,
and section reordering — all via HTMX for no full-page reloads.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from proposals.permissions import proposal_permission_required
from proposals.models import Document, DocumentSection


@proposal_permission_required(action='read')
def document_editor(request, doc_id):
    """Main Word-style document editor view."""
    org = getattr(request, 'organization', None)
    document = get_object_or_404(Document, pk=doc_id, organisation=org)
    sections = document.sections.filter(is_visible=True).order_by('order')

    active_job_id = request.GET.get('job_id') or None

    context = {
        'document': document,
        'sections': sections,
        'page_title': f'Edit — {document.title}',
        'active_job_id': active_job_id,
    }
    return render(request, 'proposals/editor/editor.html', context)


@require_POST
@proposal_permission_required(action='update')
def section_save(request, doc_id, section_id):
    """Auto-save a section's content (called via HTMX)."""
    org = getattr(request, 'organization', None)
    document = get_object_or_404(Document, pk=doc_id, organisation=org)
    section = get_object_or_404(DocumentSection, pk=section_id, document=document)

    content_html = request.POST.get('content_html', '')
    title = request.POST.get('title', section.title)

    section.content_html = content_html
    section.title = title
    section.last_edited_by = request.user
    section.save(update_fields=['content_html', 'title', 'last_edited_by', 'updated_at'])

    return JsonResponse({'status': 'success', 'section_id': section.id, 'title': section.title})


@require_POST
@proposal_permission_required(action='update')
def section_regenerate(request, doc_id, section_id):
    """Regenerate a section's content via AI (called via HTMX)."""
    org = getattr(request, 'organization', None)
    document = get_object_or_404(Document, pk=doc_id, organisation=org)
    section = get_object_or_404(DocumentSection, pk=section_id, document=document)

    from proposals.services.ai_text import regenerate_section_sync
    from proposals.models import AIJob

    job = AIJob.objects.create(
        document=document,
        job_type=AIJob.JOB_SECTION_TEXT,
        status=AIJob.STATUS_PENDING,
        triggered_by=request.user,
    )

    try:
        regenerate_section_sync(section, request.user.pk, job=job)
        # Return the updated section partial
        return render(request, 'proposals/editor/section.html', {
            'section': section,
            'document': document,
        })
    except Exception as e:
        return HttpResponse(f'<span class="text-danger">Error: {e}</span>', status=500)


@require_POST
@proposal_permission_required(action='update')
def section_reorder(request, doc_id):
    """Reorder sections via drag-and-drop (called via HTMX/AJAX)."""
    org = getattr(request, 'organization', None)
    document = get_object_or_404(Document, pk=doc_id, organisation=org)

    import json
    try:
        order_data = json.loads(request.body)
        section_ids = order_data.get('section_ids', [])
        for index, sid in enumerate(section_ids):
            DocumentSection.objects.filter(
                pk=sid, document=document
            ).update(order=index)
        return JsonResponse({'status': 'ok'})
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid data'}, status=400)


@require_POST
@proposal_permission_required(action='update')
def save_all_sections(request, doc_id):
    """Save all section content in one request (called by the manual Save button).

    Expects a JSON body:
        {"sections": [{"id": 1, "title": "...", "content_html": "..."}, ...]}
    """
    import json
    org = getattr(request, 'organization', None)
    document = get_object_or_404(Document, pk=doc_id, organisation=org)

    try:
        payload = json.loads(request.body)
        sections_data = payload.get('sections', [])
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    saved = 0
    for item in sections_data:
        sid = item.get('id')
        if not sid:
            continue
        try:
            section = DocumentSection.objects.get(pk=sid, document=document)
            section.content_html = item.get('content_html', section.content_html)
            section.title = item.get('title', section.title)
            section.last_edited_by = request.user
            section.save(update_fields=['content_html', 'title', 'last_edited_by', 'updated_at'])
            saved += 1
        except DocumentSection.DoesNotExist:
            continue

    return JsonResponse({'status': 'ok', 'saved': saved})


@proposal_permission_required(action='delete')
def document_delete(request, doc_id):
    """Delete a document (POST confirms, GET shows confirmation page)."""
    org = getattr(request, 'organization', None)
    document = get_object_or_404(Document, pk=doc_id, organisation=org)

    if request.method == 'POST':
        document.delete()
        return redirect('proposals:document_list')

    # GET — render a simple confirmation page
    return render(request, 'proposals/document_confirm_delete.html', {
        'document': document,
        'page_title': f'Delete — {document.title}',
    })
