"""
Wizard views — multi-step intake wizard for creating new documents.

The wizard collects document type, content mode, brand selection, AI-powered
intake questions, reference uploads, and a review step before generating.
Session state tracks progress across steps.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from proposals.permissions import proposal_permission_required, filter_proposals_by_scope
from proposals.models import Document, BrandGuideline, Asset
from proposals.config import PROPOSALS_CONFIG


@proposal_permission_required(action='read')
def document_list(request):
    """Landing page — list all documents for the current user/org."""
    documents = filter_proposals_by_scope(
        Document.objects.all(), request.user
    ).select_related('brand_guideline', 'created_by')

    context = {
        'documents': documents,
        'page_title': 'Proposal Maker',
    }
    return render(request, 'proposals/document_list.html', context)


@proposal_permission_required(action='create')
def wizard_start(request):
    """Initialize a new wizard session and redirect to step 1."""
    # Clear any existing wizard state
    request.session.pop('proposal_wizard', None)
    request.session['proposal_wizard'] = {
        'current_step': 1,
        'doc_type': '',
        'content_mode': '',
        'brand_id': None,
        'wizard_answers': {},
        'reference_asset_ids': [],
        'title': '',
        'recipient_name': '',
        'recipient_context': '',
    }
    return redirect('proposals:wizard_step', step=1)


@proposal_permission_required(action='create')
def wizard_step(request, step):
    """Render the wizard step template."""
    wizard_data = request.session.get('proposal_wizard', {})
    org = getattr(request, 'organization', None)

    context = {
        'step': step,
        'total_steps': 6,
        'wizard_data': wizard_data,
        'page_title': f'Create Proposal — Step {step}',
    }

    # Step-specific context
    if step == 1:
        # Document type selection
        context['doc_types'] = Document.DOC_TYPE_CHOICES
    elif step == 2:
        # Content mode
        context['content_modes'] = Document.CONTENT_MODE_CHOICES
    elif step == 3:
        # Brand selection
        if org:
            context['brands'] = BrandGuideline.objects.filter(organisation=org)
        else:
            context['brands'] = BrandGuideline.objects.none()
    elif step == 4:
        # AI-powered dynamic questions (loaded via HTMX)
        context['questions'] = wizard_data.get('generated_questions', [])
    elif step == 5:
        # Reference uploads
        context['uploaded_assets'] = []
    elif step == 6:
        # Review & confirm
        if wizard_data.get('brand_id'):
            try:
                context['selected_brand'] = BrandGuideline.objects.get(pk=wizard_data['brand_id'])
            except BrandGuideline.DoesNotExist:
                pass

    template_map = {
        1: 'proposals/wizard/step_type.html',
        2: 'proposals/wizard/step_content_mode.html',
        3: 'proposals/wizard/step_brand.html',
        4: 'proposals/wizard/step_questions.html',
        5: 'proposals/wizard/step_references.html',
        6: 'proposals/wizard/step_review.html',
    }

    template = template_map.get(step, 'proposals/wizard/step_type.html')
    return render(request, template, context)


@proposal_permission_required(action='create')
def wizard_save_step(request, step):
    """Save wizard step data to session (called via HTMX/AJAX)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    wizard_data = request.session.get('proposal_wizard', {})

    if step == 1:
        wizard_data['doc_type'] = request.POST.get('doc_type', '')
    elif step == 2:
        wizard_data['content_mode'] = request.POST.get('content_mode', '')
    elif step == 3:
        brand_id = request.POST.get('brand_id')
        wizard_data['brand_id'] = int(brand_id) if brand_id else None
    elif step == 4:
        # Collect dynamic intake answers
        answers = {}
        for key, value in request.POST.items():
            if key.startswith('question_'):
                answers[key] = value
        wizard_data['wizard_answers'] = answers
        wizard_data['title'] = request.POST.get('title', '')
        wizard_data['recipient_name'] = request.POST.get('recipient_name', '')
        wizard_data['recipient_context'] = request.POST.get('recipient_context', '')
    elif step == 5:
        # Handle file uploads
        org = getattr(request, 'organization', None)
        asset_ids = wizard_data.get('reference_asset_ids', [])
        for f in request.FILES.getlist('reference_files'):
            asset = Asset.objects.create(
                organisation=org,
                asset_type=Asset.TYPE_REFERENCE_DOC,
                file=f,
                original_filename=f.name,
                uploaded_by=request.user,
            )
            asset_ids.append(asset.pk)
        wizard_data['reference_asset_ids'] = asset_ids

    wizard_data['current_step'] = step + 1
    request.session['proposal_wizard'] = wizard_data
    request.session.modified = True

    # Return next step or stay on current
    next_step = min(step + 1, 6)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('content-type') == 'application/json':
        return JsonResponse({'status': 'success', 'next_step': next_step})
    else:
        return redirect('proposals:wizard_step', step=next_step)


@proposal_permission_required(action='create')
def wizard_generate(request):
    """Generate the document from wizard data and redirect to editor."""
    if request.method != 'POST':
        return redirect('proposals:wizard_step', step=1)

    wizard_data = request.session.get('proposal_wizard', {})
    org = getattr(request, 'organization', None)

    if not org:
        messages.error(
            request,
            'No organisation found for your account. '
            'Please log out and log back in, or contact your administrator.'
        )
        return redirect('proposals:document_list')

    # Create the document
    brand = None
    if wizard_data.get('brand_id'):
        try:
            brand = BrandGuideline.objects.get(
                pk=wizard_data['brand_id'], organisation=org
            )
        except BrandGuideline.DoesNotExist:
            pass

    document = Document.objects.create(
        organisation=org,
        title=wizard_data.get('title', 'Untitled Proposal'),
        doc_type=wizard_data.get('doc_type', Document.TYPE_PROPOSAL),
        content_mode=wizard_data.get('content_mode', Document.MODE_TEXT_ONLY),
        status=Document.STATUS_GENERATING,
        brand_guideline=brand,
        recipient_name=wizard_data.get('recipient_name', ''),
        recipient_context=wizard_data.get('recipient_context', ''),
        wizard_answers=wizard_data.get('wizard_answers', {}),
        created_by=request.user,
    )

    # Link reference assets to this document
    asset_ids = wizard_data.get('reference_asset_ids', [])
    if asset_ids:
        Asset.objects.filter(pk__in=asset_ids, organisation=org).update(document=document)
        
    if request.POST.get('custom_prompt'):
        doc_answers = document.wizard_answers or {}
        doc_answers['custom_prompt'] = request.POST.get('custom_prompt')
        document.wizard_answers = doc_answers
        document.save(update_fields=['wizard_answers'])

    # Prevent duplicate generation jobs
    from proposals.models import AIJob
    from django.urls import reverse
    
    existing_job = AIJob.objects.filter(
        document=document,
        job_type=AIJob.JOB_FULL_DOCUMENT,
        status__in=[AIJob.STATUS_PENDING, AIJob.STATUS_RUNNING],
    ).first()
    if existing_job:
        editor_url = reverse('proposals:document_editor', kwargs={'doc_id': document.pk})
        return redirect(f'{editor_url}?job_id={existing_job.pk}')

    # Trigger AI generation (sync or async)
    from proposals.config import get_config

    # Extract target pages from wizard answers
    target_pages = None
    answers = wizard_data.get('wizard_answers', {})
    for key in ('question_page_count', 'question_pages', 'question_document_length'):
        if answers.get(key):
            try:
                target_pages = int(str(answers[key]).split()[0])
                break
            except (ValueError, TypeError):
                pass

    generation_type = request.POST.get('generation_type', 'simple')

    job = AIJob.objects.create(
        document=document,
        job_type=AIJob.JOB_FULL_DOCUMENT,
        status=AIJob.STATUS_PENDING,
        triggered_by=request.user,
    )

    if get_config('ENABLE_CELERY'):
        from proposals.tasks import generate_document_task
        generate_document_task.delay(document.pk, request.user.pk, target_pages=target_pages, generation_type=generation_type)
    else:
        # Synchronous generation — catch errors so user lands in editor
        try:
            from proposals.services.ai_text import generate_document_sync
            generate_document_sync(document, request.user.pk, job=job, target_pages=target_pages, generation_type=generation_type)
        except ValueError as e:
            # Missing API key — document created but not generated
            messages.warning(
                request,
                f'Document created but AI generation skipped: {e}. '
                'Add your ANTHROPIC_API_KEY to .env and regenerate sections manually.'
            )
            document.status = Document.STATUS_DRAFT
            document.save(update_fields=['status', 'updated_at'])
        except Exception as e:
            messages.warning(
                request,
                f'Document created but AI generation failed: {e}. '
                'You can edit sections manually or try regenerating.'
            )
            document.status = Document.STATUS_DRAFT
            document.save(update_fields=['status', 'updated_at'])

    # Clear wizard session
    request.session.pop('proposal_wizard', None)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('content-type') == 'application/json':
        return JsonResponse({'status': 'success', 'document_id': document.pk, 'job_id': job.pk})
    else:
        from django.urls import reverse
        editor_url = reverse('proposals:document_editor', kwargs={'doc_id': document.pk})
        return redirect(f'{editor_url}?job_id={job.pk}')
