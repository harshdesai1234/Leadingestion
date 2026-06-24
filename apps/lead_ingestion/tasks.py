import json
import logging
import requests
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from celery import shared_task

from lead_ingestion.models import RawLead, ParsedLead, TenantIngestionConfig
from lead_ingestion.parser import parse_lead, ParseError
from lead_ingestion.signals import lead_parsed

ALLOWED_SOURCES = {'linkedin', 'instagram', 'facebook', 'google_ads', 'youtube', 'website', 'webhook', 'other'}

logger = logging.getLogger(__name__)


@shared_task
def process_pending_leads():
    """
    Celery Beat task running periodically to batch-process pending leads.
    Runs every 5 minutes globally; respects each tenant's batch_minutes cadence.
    """
    now = timezone.now()
    configs = TenantIngestionConfig.objects.filter(is_active=True).select_related('tenant')

    for config in configs:
        tenant = config.tenant

        oldest_pending = RawLead.objects.filter(
            tenant=tenant,
            status=RawLead.STATUS_PENDING,
        ).order_by('received_at').first()

        if not oldest_pending:
            continue

        time_elapsed = now - oldest_pending.received_at
        if time_elapsed < timedelta(minutes=config.batch_minutes):
            logger.info(
                f"Skipping batch for tenant {tenant.id} ({tenant.name}). "
                f"Oldest pending lead received {time_elapsed.total_seconds() / 60:.1f}m ago "
                f"(batch_minutes={config.batch_minutes})."
            )
            continue

        logger.info(f"Processing lead ingestion batch for tenant {tenant.id} ({tenant.name}).")
        try:
            process_tenant_batch(tenant, config)
        except Exception as e:
            logger.error(f"Error processing batch for tenant {tenant.id}: {str(e)}", exc_info=True)


def process_tenant_batch(tenant, config):
    """
    Select up to 50 pending rows per tenant with select_for_update(skip_locked=True),
    parse each, and create ParsedLead on success.
    """
    with transaction.atomic():
        leads = list(
            RawLead.objects.filter(
                tenant=tenant,
                status=RawLead.STATUS_PENDING,
            )
            .order_by('received_at')
            .select_for_update(skip_locked=True)[:50]
        )

        if not leads:
            return

        for lead in leads:
            lead.status = RawLead.STATUS_PROCESSING
        RawLead.objects.bulk_update(leads, ['status'])

    for lead in leads:
        try:
            parsed_data = parse_lead(lead.payload, tenant_id=tenant.id, source_hint=lead.source_hint)

            source = parsed_data.get('source') or ''
            if source not in ALLOWED_SOURCES:
                source = lead.source_hint if lead.source_hint in ALLOWED_SOURCES else 'other'
                parsed_data['source'] = source

            action = config.default_action
            rules = config.get_action_rules()
            if parsed_data.get('source') in rules:
                action = rules[parsed_data['source']]
            if action not in ('email', 'bdr_call'):
                action = config.default_action

            with transaction.atomic():
                parsed_lead = ParsedLead.objects.create(
                    tenant=tenant,
                    raw_lead=lead,
                    customer_name=parsed_data.get('name') or '',
                    mobile_number=parsed_data.get('phone') or '',
                    email_address=parsed_data.get('email') or '',
                    source=parsed_data.get('source') or '',
                    predefined_action=action,
                    confidence_note=parsed_data.get('confidence_note') or '',
                )

                lead.status = RawLead.STATUS_PARSED
                lead.error_detail = ''
                lead.processed_at = timezone.now()
                lead.save()

                try:
                    lead_parsed.send(sender=ParsedLead, instance=parsed_lead)
                except Exception as sig_err:
                    logger.error(f"Error in lead_parsed signal receiver: {str(sig_err)}")

        except ParseError as e:
            logger.warning(f"ParseError for RawLead {lead.id}: {str(e)}")
            _handle_failure(lead, e)
        except Exception as e:
            logger.warning(f"Failed processing RawLead {lead.id} on attempt {lead.retry_count + 1}: {str(e)}")
            _handle_failure(lead, e)


@shared_task
def requeue_failed_lead(raw_lead_id: int):
    """
    Re-queue a failed raw lead for re-processing.
    Resets status to pending and clears retry_count and error_detail.
    """
    try:
        lead = RawLead.objects.get(id=raw_lead_id, status=RawLead.STATUS_FAILED)
    except RawLead.DoesNotExist:
        logger.warning(f"Cannot requeue RawLead {raw_lead_id}: not found or not failed.")
        return False

    lead.status = RawLead.STATUS_PENDING
    lead.retry_count = 0
    lead.error_detail = ''
    lead.processed_at = None
    lead.save(update_fields=['status', 'retry_count', 'error_detail', 'processed_at'])
    logger.info(f"Re-queued RawLead {raw_lead_id} for re-processing.")
    return True


def _handle_failure(lead: RawLead, error: Exception):
    """Increment retry count. Fail permanently after 3 attempts."""
    with transaction.atomic():
        lead.refresh_from_db()
        lead.retry_count += 1
        if lead.retry_count >= 3:
            lead.status = RawLead.STATUS_FAILED
            lead.error_detail = f"Extraction failed after 3 attempts: {str(error)}"
        else:
            lead.status = RawLead.STATUS_PENDING
            lead.error_detail = f"Attempt {lead.retry_count} failed: {str(error)}"
        lead.processed_at = timezone.now()
        lead.save()


@shared_task
def trigger_ai_outbound_call(parsed_lead_id):
    """
    Simulates making an HTTP POST request to an AI Voice Provider API 
    (e.g., Vapi, Retell, Bland AI) to initiate an automated outbound call.
    """
    try:
        lead = ParsedLead.objects.select_related('tenant').get(id=parsed_lead_id)
        
        # Ensure we have a mobile number before calling
        if not lead.mobile_number:
            logger.warning(f"Cannot initiate AI call for ParsedLead {parsed_lead_id}: No mobile number.")
            return

        # Mock API Endpoint and Headers
        API_URL = "https://api.agentyne-voice.mock/v1/calls/outbound"
        HEADERS = {
            "Authorization": "Bearer YOUR_API_KEY",
            "Content-Type": "application/json"
        }
        
        # Payload configured for the Voice Agent
        payload = {
            "customer_number": lead.mobile_number,
            "customer_name": lead.customer_name or "Valued Customer",
            "context": f"Lead source: {lead.source}. Note: {lead.confidence_note}",
            "agent_id": "agent-default-bdr",
        }

        logger.info(f"Initiating AI automated call to {lead.mobile_number} for lead {lead.id}...")
        
        # In a real scenario, you would uncomment the following lines:
        # response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=10)
        # response.raise_for_status()
        
        # Simulate success
        logger.info(f"AI automated call successfully queued for lead {lead.id}.")

        # Update the lead status or log action here if needed
        # e.g., lead.status = 'Calling' 

    except ParsedLead.DoesNotExist:
        logger.error(f"Failed to initiate AI call: ParsedLead {parsed_lead_id} not found.")
    except Exception as e:
        logger.error(f"Error initiating AI outbound call for ParsedLead {parsed_lead_id}: {str(e)}", exc_info=True)
