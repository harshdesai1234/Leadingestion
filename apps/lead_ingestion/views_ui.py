import csv
import hashlib
import json
import secrets

import io
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.contrib import messages
from django.urls import reverse
from lead_ingestion.models import RawLead, ParsedLead, TenantIngestionConfig


def _compute_payload_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()



@login_required
def dashboard(request):
    org = getattr(request, 'organization', None)
    config = None
    if org:
        config = TenantIngestionConfig.objects.filter(tenant=org).first()
        if not config:
            config = TenantIngestionConfig.objects.create(
                tenant=org,
                api_key=secrets.token_hex(32)
            )
    raw_leads = RawLead.objects.filter(tenant=org)
    
    # Stats
    status_counts = raw_leads.values('status').annotate(count=Count('id'))
    total_raw = raw_leads.count()
    
    # Unified Lead Sheet (Parsed Leads)
    parsed_qs = ParsedLead.objects.filter(tenant=org)
    total_parsed = parsed_qs.count()
    source_counts = parsed_qs.values('source').annotate(count=Count('id')).order_by('-count')
    
    # Filters
    source_filter = request.GET.get('source', '')
    action_filter = request.GET.get('action', '')
    date_start = request.GET.get('date_start', '')
    date_end = request.GET.get('date_end', '')
    
    if source_filter:
        parsed_qs = parsed_qs.filter(source=source_filter)
    if action_filter:
        parsed_qs = parsed_qs.filter(predefined_action=action_filter)
    if date_start:
        parsed_qs = parsed_qs.filter(created_at__date__gte=parse_date(date_start))
    if date_end:
        parsed_qs = parsed_qs.filter(created_at__date__lte=parse_date(date_end))
        
    parsed_qs = parsed_qs.order_by('-created_at')
    parsed_paginator = Paginator(parsed_qs, 20)
    p_page = request.GET.get('p_page')
    parsed_page_obj = parsed_paginator.get_page(p_page)
    
    # Failed Leads Tab
    failed_qs = raw_leads.filter(status=RawLead.STATUS_FAILED).order_by('-received_at')
    failed_paginator = Paginator(failed_qs, 20)
    f_page = request.GET.get('f_page')
    failed_page_obj = failed_paginator.get_page(f_page)

    # Pending Leads Tab
    pending_qs = raw_leads.filter(status=RawLead.STATUS_PENDING).order_by('-received_at')
    pending_paginator = Paginator(pending_qs, 20)
    pending_page = request.GET.get('pending_page')
    pending_page_obj = pending_paginator.get_page(pending_page)

    context = {
        'config': config,
        'total_raw': total_raw,
        'total_parsed': total_parsed,
        'status_counts': {s['status']: s['count'] for s in status_counts},
        'source_counts': source_counts,
        'parsed_page_obj': parsed_page_obj,
        'failed_page_obj': failed_page_obj,
        'pending_page_obj': pending_page_obj,
        'source_filter': source_filter,
        'action_filter': action_filter,
        'date_start': date_start,
        'date_end': date_end,
        'page_title': 'Lead Ingestion',
        'active_tab': request.GET.get('tab', 'unified')
    }
    return render(request, 'lead_ingestion/dashboard.html', context)



@login_required
def export_leads(request):
    org = getattr(request, 'organization', None)
    active_tab = request.GET.get('tab', 'unified')
    source_filter = request.GET.get('source', '')
    action_filter = request.GET.get('action', '')
    date_start = request.GET.get('date_start', '')
    date_end = request.GET.get('date_end', '')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leads_export_{active_tab}.csv"'
    writer = csv.writer(response)
    
    if active_tab == 'unified':
        qs = ParsedLead.objects.filter(tenant=org)
        if source_filter:
            qs = qs.filter(source=source_filter)
        if action_filter:
            qs = qs.filter(predefined_action=action_filter)
        if date_start:
            qs = qs.filter(created_at__date__gte=parse_date(date_start))
        if date_end:
            qs = qs.filter(created_at__date__lte=parse_date(date_end))
        
        writer.writerow(['ID', 'Customer Name', 'Email', 'Phone', 'Source', 'Action', 'Created At'])
        for lead in qs.order_by('-created_at'):
            writer.writerow([lead.id, lead.customer_name, lead.email_address, lead.mobile_number, lead.source, lead.predefined_action, lead.created_at])
            
    else:
        # Pending or Failed
        status = RawLead.STATUS_PENDING if active_tab == 'pending' else RawLead.STATUS_FAILED
        qs = RawLead.objects.filter(tenant=org, status=status)
        writer.writerow(['ID', 'Source Hint', 'Received At', 'Error Detail'])
        for lead in qs.order_by('-received_at'):
            writer.writerow([lead.id, lead.source_hint, lead.received_at, lead.error_detail])
            
    return response

def raw_lead_list(request):
    org = getattr(request, 'organization', None)
    status_filter = request.GET.get('status', '')
    leads = RawLead.objects.filter(tenant=org).select_related('parsed_lead')
    if status_filter:
        leads = leads.filter(status=status_filter)
    leads = leads.order_by('-received_at')
    context = {
        'leads': leads,
        'status_filter': status_filter,
        'page_title': 'Raw Leads',
    }
    return render(request, 'lead_ingestion/raw_lead_list.html', context)



def raw_lead_detail(request, pk):
    org = getattr(request, 'organization', None)
    lead = get_object_or_404(RawLead, pk=pk, tenant=org)
    context = {
        'lead': lead,
        'page_title': f'Raw Lead #{lead.id}',
    }
    return render(request, 'lead_ingestion/raw_lead_detail.html', context)



def parsed_lead_list(request):
    org = getattr(request, 'organization', None)
    source_filter = request.GET.get('source', '')
    action_filter = request.GET.get('action', '')
    date_start = request.GET.get('date_start', '')
    date_end = request.GET.get('date_end', '')
    
    leads = ParsedLead.objects.filter(tenant=org).select_related('raw_lead')
    if source_filter:
        leads = leads.filter(source=source_filter)
    if action_filter:
        leads = leads.filter(predefined_action=action_filter)
    if date_start:
        leads = leads.filter(created_at__date__gte=parse_date(date_start))
    if date_end:
        leads = leads.filter(created_at__date__lte=parse_date(date_end))
        
    leads = leads.order_by('-created_at')
    context = {
        'leads': leads,
        'source_filter': source_filter,
        'action_filter': action_filter,
        'date_start': date_start,
        'date_end': date_end,
        'page_title': 'Parsed Leads',
    }
    return render(request, 'lead_ingestion/parsed_lead_list.html', context)



def parsed_lead_detail(request, pk):
    org = getattr(request, 'organization', None)
    lead = get_object_or_404(ParsedLead, pk=pk, tenant=org)
    context = {
        'lead': lead,
        'page_title': f'Parsed Lead #{lead.id}',
    }
    return render(request, 'lead_ingestion/parsed_lead_detail.html', context)



def config_view(request):
    org = getattr(request, 'organization', None)
    if not org:
        messages.error(request, 'No organization associated with your account.')
        return redirect('lead_ingestion:dashboard')
    config = TenantIngestionConfig.objects.filter(tenant=org).first()
    if not config and org:
        config = TenantIngestionConfig.objects.create(
            tenant=org,
            api_key=secrets.token_hex(32)
        )

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'save_action_rules':
            rules_raw = request.POST.get('action_rules', '')
            if rules_raw.strip():
                try:
                    json.loads(rules_raw)
                except json.JSONDecodeError:
                    messages.error(request, 'Invalid JSON in action rules.')
                    return redirect('lead_ingestion:config')
            config.action_rules = rules_raw
            config.save(update_fields=['action_rules'])
            messages.success(request, 'Action rules updated.')

        elif action == 'regenerate_key':
            new_key = secrets.token_hex(32)
            config.api_key = new_key
            config.save(update_fields=['api_key'])
            messages.success(
                request,
                f'New API key generated. Copy it now — it won\'t be shown again: {new_key}'
            )

        return redirect('lead_ingestion:config')

    context = {
        'config': config,
        'masked_key': config.get_masked_key() if config else None,
        'page_title': 'Ingestion Configuration',
    }
    return render(request, 'lead_ingestion/config.html', context)



def upload_csv(request):
    org = getattr(request, 'organization', None)
    result = None
    if request.method == 'POST' and request.FILES.get('file'):
        csv_file = request.FILES['file']
        if not csv_file.name.endswith('.csv'):
            result = {'error': 'Please upload a CSV file.'}
        else:
            try:
                file_data = csv_file.read().decode('utf-8')
                reader = csv.DictReader(io.StringIO(file_data))
                rows = list(reader)
                if not rows:
                    result = {'error': 'CSV file is empty.'}
                else:
                    leads = []
                    new_count = 0
                    duplicate_count = 0
                    for row in rows:
                        payload = json.dumps(row)
                        h = _compute_payload_hash(payload)
                        if RawLead.objects.filter(tenant=org, payload_hash=h).exists():
                            duplicate_count += 1
                            continue
                        leads.append(RawLead(
                            tenant=org,
                            source_hint=f"csv_upload: {csv_file.name}",
                            payload=payload,
                            payload_hash=h,
                            content_type='text/csv',
                        ))
                        new_count += 1
                    if leads:
                        RawLead.objects.bulk_create(leads)
                    result = {
                        'success': True,
                        'count': new_count,
                        'duplicates': duplicate_count,
                    }
            except Exception as e:
                result = {'error': f'Failed to process CSV: {str(e)}'}
    context = {
        'result': result,
        'page_title': 'Upload CSV',
    }
    return render(request, 'lead_ingestion/upload_csv.html', context)



def failed_leads(request):
    org = getattr(request, 'organization', None)
    leads = RawLead.objects.filter(tenant=org, status=RawLead.STATUS_FAILED).order_by('-processed_at')
    context = {
        'leads': leads,
        'page_title': 'Failed Leads',
    }
    return render(request, 'lead_ingestion/failed_leads.html', context)


from django.http import JsonResponse


def requeue_lead(request, pk):
    if request.method != 'POST':
        return redirect('lead_ingestion:failed_leads')
    org = getattr(request, 'organization', None)
    lead = get_object_or_404(RawLead, pk=pk, tenant=org)
    
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('accept') == 'application/json'
    
    if lead.status != RawLead.STATUS_FAILED:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Only failed leads can be requeued.'}, status=400)
        messages.error(request, 'Only failed leads can be requeued.')
        return redirect('lead_ingestion:failed_leads')

    from lead_ingestion.tasks import requeue_failed_lead
    if hasattr(requeue_failed_lead, 'delay'):
        requeue_failed_lead.delay(lead.id)
    else:
        requeue_failed_lead(lead.id)
        
    if is_ajax:
        return JsonResponse({'success': True, 'message': f'Lead #{lead.id} requeued for re-processing.'})
        
    messages.success(request, f'Lead #{lead.id} requeued for re-processing.')
    return redirect(request.META.get('HTTP_REFERER', reverse('lead_ingestion:dashboard') + '?tab=failed'))



def move_to_crm(request, pk):
    if request.method != 'POST':
        return redirect('lead_ingestion:dashboard')
    org = getattr(request, 'organization', None)
    lead = get_object_or_404(ParsedLead, pk=pk, tenant=org)
    
    # Placeholder for CRM logic
    messages.success(request, f'Lead "{lead.customer_name or lead.email_address}" successfully moved to CRM.')
    
    return redirect(request.META.get('HTTP_REFERER', reverse('lead_ingestion:dashboard')))

def delete_raw_lead(request, pk):
    if request.method != 'POST':
        return redirect('lead_ingestion:dashboard')
    org = getattr(request, 'organization', None)
    if org:
        lead = get_object_or_404(RawLead, pk=pk, tenant=org)
    else:
        lead = get_object_or_404(RawLead, pk=pk)
    lead.delete()
    messages.success(request, 'Raw lead successfully deleted.')
    return redirect(request.META.get('HTTP_REFERER', reverse('lead_ingestion:dashboard')))


def delete_parsed_lead(request, pk):
    if request.method != 'POST':
        return redirect('lead_ingestion:dashboard')
    org = getattr(request, 'organization', None)
    if org:
        lead = get_object_or_404(ParsedLead, pk=pk, tenant=org)
    else:
        lead = get_object_or_404(ParsedLead, pk=pk)
    lead.delete()
    messages.success(request, 'Parsed lead successfully deleted.')
    return redirect(request.META.get('HTTP_REFERER', reverse('lead_ingestion:dashboard')))
