import csv
import hashlib
import io
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from lead_ingestion.auth import TenantAPIKeyAuthentication
from lead_ingestion.models import RawLead, ParsedLead, TenantIngestionConfig
import logging

logger = logging.getLogger(__name__)


def _compute_payload_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _is_duplicate(tenant, payload: str) -> bool:
    h = _compute_payload_hash(payload)
    return RawLead.objects.filter(
        tenant=tenant, payload_hash=h
    ).exists()


class WebhookIngestionView(APIView):
    """
    Endpoint for receiving webhook payloads.
    Stores the raw body verbatim with status='pending'.
    Deduplicates by payload hash (SHA-256) per tenant.
    """
    authentication_classes = []
    permission_classes = []
    parser_classes = [JSONParser]

    def get(self, request, source=None, *args, **kwargs):
        """
        Handle Meta (Facebook/Instagram) Webhook Verification.
        Meta sends a GET request with hub.mode, hub.challenge, and hub.verify_token.
        """
        mode = request.query_params.get('hub.mode')
        challenge = request.query_params.get('hub.challenge')
        
        if mode == 'subscribe' and challenge:
            from django.http import HttpResponse
            return HttpResponse(challenge, status=200)
            
        return Response({"error": "Invalid GET request."}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, source=None, *args, **kwargs):
        raw_body = request.body.decode('utf-8')

        tenant = getattr(request, 'organization', None)
        if not tenant:
            config = TenantIngestionConfig.objects.filter(is_active=True).order_by('tenant_id').first()
            if not config:
                return Response({"error": "No active tenant configuration available."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            tenant = config.tenant

        if _is_duplicate(tenant, raw_body):
            h = _compute_payload_hash(raw_body)
            existing = RawLead.objects.filter(
                tenant=tenant, payload_hash=h
            ).first()
            logger.info(f"raw_lead_id={existing.id} status_code=202 duplicate=True")
            return Response(
                {
                    "raw_lead_id": existing.id,
                    "status": "pending",
                    "message": "Lead payload received and queued for processing.",
                    "duplicate": True
                },
                status=status.HTTP_202_ACCEPTED
            )

        source_hint = source if source else 'webhook'
        raw_lead = RawLead.objects.create(
            tenant=tenant,
            source_hint=source_hint,
            payload=raw_body,
            content_type=request.content_type or 'application/json',
            payload_hash=_compute_payload_hash(raw_body),
            status=RawLead.STATUS_PENDING
        )

        import threading
        from lead_ingestion.tasks import process_tenant_batch
        import time

        def trigger_processing():
            time.sleep(1)
            config = TenantIngestionConfig.objects.filter(tenant=tenant).first()
            if config:
                while RawLead.objects.filter(tenant=tenant, status=RawLead.STATUS_PENDING).exists():
                    process_tenant_batch(tenant, config)

        threading.Thread(target=trigger_processing).start()

        logger.info(f"raw_lead_id={raw_lead.id} status_code=202 duplicate=False")
        return Response(
            {
                "raw_lead_id": raw_lead.id,
                "status": "pending",
                "message": "Lead payload received and queued for processing."
            },
            status=status.HTTP_202_ACCEPTED
        )


class FormIngestionView(APIView):
    """
    Endpoint for receiving form-submitted leads (JSON or urlencoded).
    Stores the raw body verbatim with status='pending'.
    Deduplicates by payload hash per tenant.
    """
    authentication_classes = []
    permission_classes = []
    parser_classes = [FormParser, MultiPartParser, JSONParser]

    def post(self, request, *args, **kwargs):
        raw_body = request.body.decode('utf-8')

        tenant = getattr(request, 'organization', None)
        if not tenant:
            config = TenantIngestionConfig.objects.filter(is_active=True).order_by('tenant_id').first()
            if not config:
                return Response({"error": "No active tenant configuration available."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            tenant = config.tenant

        if _is_duplicate(tenant, raw_body):
            h = _compute_payload_hash(raw_body)
            existing = RawLead.objects.filter(
                tenant=tenant, payload_hash=h
            ).first()
            logger.info(f"raw_lead_id={existing.id} status_code=202 duplicate=True")
            return Response(
                {
                    "raw_lead_id": existing.id,
                    "status": "pending",
                    "message": "Lead payload received and queued for processing.",
                    "duplicate": True
                },
                status=status.HTTP_202_ACCEPTED
            )

        raw_lead = RawLead.objects.create(
            tenant=tenant,
            source_hint='form',
            payload=raw_body,
            content_type=request.content_type or 'application/x-www-form-urlencoded',
            payload_hash=_compute_payload_hash(raw_body),
            status=RawLead.STATUS_PENDING
        )

        import threading
        from lead_ingestion.tasks import process_tenant_batch
        import time

        def trigger_processing():
            time.sleep(1)
            config = TenantIngestionConfig.objects.filter(tenant=tenant).first()
            if config:
                while RawLead.objects.filter(tenant=tenant, status=RawLead.STATUS_PENDING).exists():
                    process_tenant_batch(tenant, config)

        threading.Thread(target=trigger_processing).start()

        logger.info(f"raw_lead_id={raw_lead.id} status_code=202 duplicate=False")
        return Response(
            {
                "raw_lead_id": raw_lead.id,
                "status": "pending",
                "message": "Lead payload received and queued for processing."
            },
            status=status.HTTP_202_ACCEPTED
        )


class CSVIngestionView(APIView):
    """
    Endpoint for uploading a CSV file.
    Each row in the CSV is stored as a separate RawLead with status='pending'.
    Deduplicates by payload hash per tenant.
    """
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response(
                {"error": "No file uploaded. Please upload a CSV file with the key 'file'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not csv_file.name.endswith('.csv'):
            return Response(
                {"error": "Invalid file format. Please upload a CSV file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            file_data = csv_file.read().decode('utf-8')
            csv_data = io.StringIO(file_data)

            reader = csv.DictReader(csv_data)

            if not reader.fieldnames:
                csv_data.seek(0)
                fallback_reader = csv.reader(csv_data)
                rows = list(fallback_reader)
                raw_leads_data = [json.dumps(row) for row in rows]
            else:
                raw_leads_data = [json.dumps(row) for row in reader]

            if not raw_leads_data:
                return Response(
                    {"error": "The uploaded CSV file is empty."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            tenant = getattr(request, 'organization', None)
            if not tenant:
                config = TenantIngestionConfig.objects.filter(is_active=True).order_by('tenant_id').first()
                if not config:
                    return Response({"error": "No active tenant configuration available."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                tenant = config.tenant
                
            created_leads = []
            new_count = 0
            duplicate_count = 0
            existing_ids = []
            seen_hashes = set()

            for row_payload in raw_leads_data:
                h = _compute_payload_hash(row_payload)
                if h in seen_hashes or RawLead.objects.filter(
                    tenant=tenant, payload_hash=h
                ).exists():
                    duplicate_count += 1
                    continue

                seen_hashes.add(h)
                lead = RawLead(
                    tenant=tenant,
                    source_hint=f"csv_upload: {csv_file.name}",
                    payload=row_payload,
                    payload_hash=h,
                    content_type='text/csv',
                    status=RawLead.STATUS_PENDING
                )
                created_leads.append(lead)
                new_count += 1

            if created_leads:
                RawLead.objects.bulk_create(created_leads)
                db_leads = RawLead.objects.filter(
                    tenant=tenant,
                    source_hint=f"csv_upload: {csv_file.name}",
                    status=RawLead.STATUS_PENDING
                ).order_by('-received_at')[:new_count]
                lead_ids = [lead.id for lead in reversed(db_leads)]
            else:
                lead_ids = []

            all_ids = lead_ids + existing_ids

            is_duplicate = (new_count == 0 and duplicate_count > 0)
            logger.info(f"raw_lead_id={all_ids[0] if all_ids else None} status_code=202 duplicate={is_duplicate}")

            import threading
            from lead_ingestion.tasks import process_tenant_batch
            import time

            def trigger_processing():
                time.sleep(1)
                config = TenantIngestionConfig.objects.filter(tenant=tenant).first()
                if config:
                    while RawLead.objects.filter(tenant=tenant, status=RawLead.STATUS_PENDING).exists():
                        process_tenant_batch(tenant, config)

            threading.Thread(target=trigger_processing).start()
            
            return Response(
                {
                    "raw_lead_ids": all_ids,
                    "raw_lead_id": all_ids[0] if all_ids else None,
                    "status": "pending",
                    "message": "Lead payload received and queued for processing.",
                    "duplicate": is_duplicate
                },
                status=status.HTTP_202_ACCEPTED
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to process CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
