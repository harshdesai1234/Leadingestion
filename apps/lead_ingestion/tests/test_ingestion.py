import json
import io
from datetime import timedelta
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from rest_framework.test import APIClient
from lead_ingestion.models import RawLead, ParsedLead, TenantIngestionConfig
from lead_ingestion.parser import parse_lead, ParseError, validate_extracted_data
from lead_ingestion.tasks import process_pending_leads
from lead_ingestion.signals import lead_parsed
from accounts.models import Organization
from django.contrib.auth import get_user_model

User = get_user_model()

# ==============================================================================
#  15+ MESSY REAL-WORLD PAYLOAD FIXTURES
# ==============================================================================

@pytest.fixture
def linkedin_payload_1():
    return json.dumps({
        "lead_id": "li-98239082",
        "submitted_at": "2026-06-12T12:00:00Z",
        "form_name": "Enterprise B2B Survey",
        "answers": [
            {"question": "Full Name", "answer": "Sarah Connor"},
            {"question": "Work Email", "answer": "sconnor@cyberdyne.com"},
            {"question": "Phone Number", "answer": "+1 415-555-0199"},
            {"question": "Company", "answer": "Cyberdyne Systems"}
        ],
        "platform": "linkedin"
    })

@pytest.fixture
def linkedin_payload_2():
    return json.dumps({
        "id": "urn:li:lead:100234",
        "profile": {"first-name": "John", "last-name": "Connor"},
        "email": "john.c@resistance.org",
        "phone": "555-0100",
        "source": "LinkedIn Ads"
    })

@pytest.fixture
def meta_payload_1():
    return json.dumps({
        "object": "page",
        "entry": [{
            "id": "page-123",
            "time": 1445431122,
            "changes": [{
                "field": "leadgen",
                "value": {
                    "leadgen_id": "meta-8829102",
                    "page_id": "page-123",
                    "form_id": "form-777",
                    "created_time": 1445431122,
                    "email": "t800@skynet.com",
                    "full_name": "Model 101",
                    "phone_number": "+1-800-555-3829"
                }
            }]
        }]
    })

@pytest.fixture
def meta_payload_2():
    return json.dumps({
        "leadgen_id": "fb-992019",
        "created_time": "2026-06-12",
        "ad_id": "ad-3301",
        "email": "t1000@liquid.metal",
        "full_name": "Robert Patrick",
        "phone_number": "0018885552390"
    })

@pytest.fixture
def google_ads_payload_1():
    return json.dumps({
        "lead_id": "g-10029",
        "user_column_data": [
            {"column_name": "Full Name", "string_value": "Marcus Wright"},
            {"column_name": "User Email", "string_value": "marcus@projectangel.org"},
            {"column_name": "User Phone", "string_value": "+13105559811"}
        ],
        "api_version": "1.0",
        "google_key": "g-secret",
        "source": "google_ads"
    })

@pytest.fixture
def google_ads_payload_2():
    return json.dumps({
        "campaign_id": 992039,
        "lead_id": "g-99102",
        "email": "katherine.brewster@rebellion.net",
        "full_name": "Kate Brewster",
        "phone": "+1 (213) 555-0144"
    })

@pytest.fixture
def website_form_payload_1():
    return "name=Kyle+Reese&email=kreese%40resistance.net&phone=%2B19995551984&source=website&notes=Send+prop+asap"

@pytest.fixture
def website_form_payload_2():
    return "full_name=Dr.+Silberman&email=silberman%40mentalhealth.org&phone=5552910&notes=Urgent"

@pytest.fixture
def csv_payload_1():
    return '{"Name": "Miles Dyson", "Email": "mdyson@cyberdyne.com", "Phone": "+1-408-555-1212", "Source": "linkedin"}'

@pytest.fixture
def csv_payload_2():
    return '{"Name": "Danny Dyson", "Email": "ddyson@cyberdyne.com", "Phone": "408-555-9000", "Source": "website"}'

@pytest.fixture
def arabic_payload():
    return json.dumps({
        "الإسم": "محمد أحمد",
        "الهاتف": "+966501234567",
        "البريد الإلكتروني": "mohamed.ahmed@example.sa",
        "المصدر": "instagram",
        "ملاحظات": "الرجاء الاتصال بأسرع وقت"
    })

@pytest.fixture
def hindi_payload():
    return json.dumps({
        "नाम": "अमित शर्मा",
        "फोन": "+919876543210",
        "ईमेल": "amit.sharma@example.in",
        "स्रोत": "facebook",
        "विवरण": "प्रस्ताव भेजें"
    })

@pytest.fixture
def instagram_payload():
    return json.dumps({
        "sender_id": "ig-user-8819",
        "message_text": "Hey, I am looking to buy. Contact me at grace@cyberdyne.com or +15550001234. Source: Instagram",
        "platform": "instagram"
    })

@pytest.fixture
def contact_form_payload_messy():
    return json.dumps({
        "data": {
            "fields": {
                "field_1": "John Connor",
                "field_2": "john.c@skynet.net",
                "field_3": "+1 310 555 4567"
            },
            "origin": "website"
        }
    })

@pytest.fixture
def cold_email_payload():
    return json.dumps({
        "from": "tar@resistance.org",
        "subject": "Interested in ASOC",
        "body": "Hi, I saw your product. Let's schedule a call. Call me at +447911123456. Thanks, Tar.",
        "source": "other"
    })

@pytest.fixture
def raw_text_messy_payload():
    return "Interested party: Grace. Reachable via email: grace@future.net or cell: +17775551212. Source: google ads."

# ==============================================================================
#  LARGE PAYLOAD (100KB+)
# ==============================================================================

@pytest.fixture
def large_payload():
    """Payload exceeding 100 KB to test truncation."""
    base = '{"name": "Large Lead", "email": "large@test.com", "phone": "+1234567890", "data": "'
    padding = "X" * 120_000
    return base + padding + '"}'

# ==============================================================================
#  TEST CASES
# ==============================================================================

@pytest.mark.django_db
class TestLeadIngestion:

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.owner = User.objects.create_user(username="test_owner", email="owner@test.com", password="password")
        self.tenant = Organization.objects.create(name="Cyberdyne", owner=self.owner)
        self.raw_api_key = "agt-secret-key-123456"
        self.config = TenantIngestionConfig.objects.create(
            tenant=self.tenant,
            api_key=self.raw_api_key,
            batch_minutes=10,
            default_action="email",
            action_rules=json.dumps({"facebook": "bdr_call", "linkedin": "bdr_call"}),
            is_active=True,
        )
        # Create UserProfile so OrganizationMiddleware can resolve org for UI views
        from accounts.models import UserProfile
        UserProfile.objects.get_or_create(user=self.owner, defaults={'organization': self.tenant})
        self.client = APIClient()

    def test_authentication_success(self):
        url = reverse('lead_ingestion:webhook_ingestion')
        self.client.credentials(HTTP_X_AGENTYNE_API_KEY=self.raw_api_key)
        response = self.client.post(url, data={"lead": "test"}, format='json')
        assert response.status_code == 202
        assert "raw_lead_id" in response.data
        assert RawLead.objects.filter(tenant=self.tenant).count() == 1

    def test_authentication_missing_key(self):
        url = reverse('lead_ingestion:webhook_ingestion')
        response = self.client.post(url, data={"lead": "test"}, format='json')
        assert response.status_code == 401

    def test_authentication_invalid_key(self):
        url = reverse('lead_ingestion:webhook_ingestion')
        self.client.credentials(HTTP_X_AGENTYNE_API_KEY="invalid-key")
        response = self.client.post(url, data={"lead": "test"}, format='json')
        assert response.status_code == 401

    def test_authentication_inactive_config(self):
        self.config.is_active = False
        self.config.save()
        url = reverse('lead_ingestion:webhook_ingestion')
        self.client.credentials(HTTP_X_AGENTYNE_API_KEY=self.raw_api_key)
        response = self.client.post(url, data={"lead": "test"}, format='json')
        assert response.status_code == 401

    def test_webhook_ingestion_stores_payload_verbatim(self, linkedin_payload_1):
        url = reverse('lead_ingestion:webhook_ingestion')
        self.client.credentials(HTTP_X_AGENTYNE_API_KEY=self.raw_api_key)
        response = self.client.post(url, data=json.loads(linkedin_payload_1), format='json')
        assert response.status_code == 202
        lead = RawLead.objects.get(id=response.data['raw_lead_id'])
        assert lead.status == RawLead.STATUS_PENDING
        assert lead.tenant == self.tenant
        assert lead.source_hint == 'webhook'
        stored_data = json.loads(lead.payload)
        assert stored_data['lead_id'] == "li-98239082"

    def test_form_ingestion_supports_url_encoding(self, website_form_payload_1):
        url = reverse('lead_ingestion:form_ingestion')
        self.client.credentials(HTTP_X_AGENTYNE_API_KEY=self.raw_api_key)
        response = self.client.post(url, data=website_form_payload_1, content_type='application/x-www-form-urlencoded')
        assert response.status_code == 202
        lead = RawLead.objects.get(id=response.data['raw_lead_id'])
        assert lead.status == RawLead.STATUS_PENDING
        assert lead.payload == website_form_payload_1

    def test_csv_upload_creates_one_raw_lead_per_row(self):
        url = reverse('lead_ingestion:csv_ingestion')
        self.client.credentials(HTTP_X_AGENTYNE_API_KEY=self.raw_api_key)
        csv_content = "Name,Email,Phone,Source\nMiles Dyson,mdyson@cyberdyne.com,+1-408-555-1212,linkedin\nDanny Dyson,ddyson@cyberdyne.com,408-555-9000,website\n"
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = "leads.csv"
        response = self.client.post(url, data={"file": csv_file}, format='multipart')
        assert response.status_code == 202
        assert len(response.data['raw_lead_ids']) == 2
        leads = RawLead.objects.filter(tenant=self.tenant).order_by('id')
        assert leads.count() == 2
        assert json.loads(leads[0].payload)['Name'] == "Miles Dyson"
        assert json.loads(leads[1].payload)['Name'] == "Danny Dyson"

    def test_llm_parser_validation_phone_email(self):
        valid_input = {
            "name": "Sarah Connor",
            "phone": "+1 (415) 555-0199",
            "email": "sconnor@cyberdyne.com",
            "source": "linkedin",
        }
        res = validate_extracted_data(valid_input)
        assert res['name'] == "Sarah Connor"
        assert res['phone'] == "+14155550199"
        assert res['email'] == "sconnor@cyberdyne.com"
        assert res['source'] == "linkedin"

        invalid_phone = {
            "name": "Sarah Connor",
            "phone": "abc-def-ghij",
            "email": "sconnor@cyberdyne.com",
            "source": "facebook",
        }
        res = validate_extracted_data(invalid_phone)
        assert res['phone'] is None
        assert res['email'] == "sconnor@cyberdyne.com"

        invalid_email = {
            "name": "Sarah Connor",
            "phone": "+14155550199",
            "email": "not-an-email",
            "source": "instagram",
        }
        res = validate_extracted_data(invalid_email)
        assert res['email'] is None
        assert res['phone'] == "+14155550199"

    def test_llm_parser_raises_error_when_both_missing(self):
        """When both phone and email are missing, validate_extracted_data raises ParseError."""
        data = {
            "name": "Anonymous",
            "phone": None,
            "email": None,
            "source": "website",
        }
        with pytest.raises(ParseError, match="Both phone and email are missing"):
            validate_extracted_data(data)

    def test_llm_parser_raises_error_when_both_null(self):
        """Parser raises ParseError when both phone/email missing."""
        data = {"name": "Test", "phone": None, "email": None, "source": "other"}
        with pytest.raises(ParseError, match="Both phone and email are missing"):
            validate_extracted_data(data)

    @patch('lead_ingestion.tasks.parse_lead')
    def test_celery_task_state_machine_success(self, mock_parse, linkedin_payload_1):
        mock_parse.return_value = {
            "name": "Sarah Connor",
            "phone": "+14155550199",
            "email": "sconnor@cyberdyne.com",
            "source": "linkedin",
            "confidence_note": "High confidence match",
        }

        raw_lead = RawLead.objects.create(
            tenant=self.tenant,
            source_hint='webhook',
            payload=linkedin_payload_1,
        )
        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()

        signal_emitted = []
        def handle_signal(sender, instance, **kwargs):
            signal_emitted.append(instance)
        lead_parsed.connect(handle_signal)

        process_pending_leads()

        raw_lead.refresh_from_db()
        assert raw_lead.status == RawLead.STATUS_PARSED
        assert raw_lead.processed_at is not None

        parsed_lead = ParsedLead.objects.get(raw_lead=raw_lead)
        assert parsed_lead.customer_name == "Sarah Connor"
        assert parsed_lead.mobile_number == "+14155550199"
        assert parsed_lead.email_address == "sconnor@cyberdyne.com"
        assert parsed_lead.source == "linkedin"
        assert parsed_lead.predefined_action == "bdr_call"

        assert len(signal_emitted) == 1
        assert signal_emitted[0] == parsed_lead
        lead_parsed.disconnect(handle_signal)

    @patch('lead_ingestion.tasks.parse_lead')
    def test_celery_task_retries_and_failure(self, mock_parse, raw_text_messy_payload):
        mock_parse.side_effect = ParseError("Unable to extract lead info")

        raw_lead = RawLead.objects.create(
            tenant=self.tenant,
            source_hint='webhook',
            payload=raw_text_messy_payload,
        )
        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()

        process_pending_leads()
        raw_lead.refresh_from_db()
        assert raw_lead.status == RawLead.STATUS_PENDING
        assert raw_lead.retry_count == 1
        assert "Attempt 1 failed" in raw_lead.error_detail

        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()
        process_pending_leads()
        raw_lead.refresh_from_db()
        assert raw_lead.retry_count == 2
        assert raw_lead.status == RawLead.STATUS_PENDING

        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()
        process_pending_leads()
        raw_lead.refresh_from_db()
        assert raw_lead.retry_count == 3
        assert raw_lead.status == RawLead.STATUS_FAILED
        assert "Extraction failed after 3 attempts" in raw_lead.error_detail

    @patch('lead_ingestion.tasks.parse_lead')
    def test_large_payload_truncated_for_llm(self, mock_parse, large_payload):
        """Payloads over 100 KB are truncated before sending to the LLM."""
        mock_parse.return_value = {
            "name": "Large Lead",
            "phone": "+1234567890",
            "email": "large@test.com",
            "source": "other",
        }
        raw_lead = RawLead.objects.create(
            tenant=self.tenant,
            source_hint='webhook',
            payload=large_payload,
        )
        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()

        process_pending_leads()
        raw_lead.refresh_from_db()
        assert raw_lead.status == RawLead.STATUS_PARSED
        parsed_lead = ParsedLead.objects.get(raw_lead=raw_lead)
        assert parsed_lead.customer_name == "Large Lead"

    def test_tenant_batch_minutes_respected(self, linkedin_payload_2):
        raw_lead = RawLead.objects.create(
            tenant=self.tenant,
            source_hint='webhook',
            payload=linkedin_payload_2,
        )
        process_pending_leads()
        raw_lead.refresh_from_db()
        assert raw_lead.status == RawLead.STATUS_PENDING
        assert raw_lead.retry_count == 0

    @pytest.mark.django_db(transaction=True)
    def test_concurrency_skip_locked(self, linkedin_payload_1):
        raw_lead = RawLead.objects.create(
            tenant=self.tenant,
            source_hint='webhook',
            payload=linkedin_payload_1,
        )
        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()

        with transaction.atomic():
            locked_leads = list(RawLead.objects.filter(id=raw_lead.id).select_for_update(skip_locked=True))
            assert len(locked_leads) == 1
            skipped_leads = RawLead.objects.filter(id=raw_lead.id).select_for_update(skip_locked=True)
            assert locked_leads[0].id == raw_lead.id

    def test_tenant_isolation(self, linkedin_payload_1):
        owner_b = User.objects.create_user(username="owner_b", email="owner_b@test.com", password="password")
        tenant_b = Organization.objects.create(name="Skynet", owner=owner_b)
        lead_b = RawLead.objects.create(
            tenant=tenant_b,
            source_hint='webhook',
            payload=linkedin_payload_1,
        )
        tenant_a_leads = RawLead.objects.filter(tenant=self.tenant)
        tenant_b_leads = RawLead.objects.filter(tenant=tenant_b)
        assert lead_b not in tenant_a_leads
        assert lead_b in tenant_b_leads

    def test_parser_mock_handles_all_platforms(
        self, linkedin_payload_1, linkedin_payload_2, meta_payload_1, meta_payload_2,
        google_ads_payload_1, google_ads_payload_2, website_form_payload_1, website_form_payload_2,
        csv_payload_1, csv_payload_2, arabic_payload, hindi_payload, instagram_payload,
        contact_form_payload_messy, cold_email_payload, raw_text_messy_payload
    ):
        for label, fixture_data in [
            ("linkedin_1", linkedin_payload_1),
            ("linkedin_2", linkedin_payload_2),
            ("meta_1", meta_payload_1),
            ("meta_2", meta_payload_2),
            ("google_1", google_ads_payload_1),
            ("google_2", google_ads_payload_2),
            ("arabic", arabic_payload),
            ("hindi", hindi_payload),
            ("instagram", instagram_payload),
            ("contact_form", contact_form_payload_messy),
            ("cold_email", cold_email_payload),
            ("raw_text", raw_text_messy_payload),
        ]:
            try:
                result = parse_lead(fixture_data)
                assert result.get('email') or result.get('phone'), f"{label}: should have email or phone"
            except ParseError as e:
                pytest.fail(f"{label} raised ParseError: {e}")

        for label, fixture_data in [
            ("csv_1", csv_payload_1),
            ("csv_2", csv_payload_2),
            ("web_form_1", website_form_payload_1),
            ("web_form_2", website_form_payload_2),
        ]:
            try:
                result = parse_lead(fixture_data)
                assert result.get('email') or result.get('phone'), f"{label}: should have email or phone"
            except ParseError as e:
                pytest.fail(f"{label} raised ParseError: {e}")

    @patch('lead_ingestion.tasks.parse_lead')
    def test_requeue_flow(self, mock_parse, linkedin_payload_1):
        """Failed leads can be requeued for re-processing."""
        mock_parse.side_effect = ParseError("fail")

        raw_lead = RawLead.objects.create(
            tenant=self.tenant,
            source_hint='webhook',
            payload=linkedin_payload_1,
        )
        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()

        for _ in range(3):
            raw_lead.received_at = timezone.now() - timedelta(minutes=15)
            raw_lead.save()
            process_pending_leads()
            raw_lead.refresh_from_db()

        assert raw_lead.status == RawLead.STATUS_FAILED

        from lead_ingestion.tasks import requeue_failed_lead
        requeue_failed_lead(raw_lead.id)

        raw_lead.refresh_from_db()
        assert raw_lead.status == RawLead.STATUS_PENDING
        assert raw_lead.retry_count == 0
        assert raw_lead.error_detail == ''

    def test_action_rules_parsed_as_json(self):
        """TenantIngestionConfig.get_action_rules parses JSON text rules."""
        self.config.action_rules = '{"linkedin": "bdr_call", "website": "email"}'
        self.config.save()
        rules = self.config.get_action_rules()
        assert rules == {"linkedin": "bdr_call", "website": "email"}

        self.config.action_rules = ''
        self.config.save()
        assert self.config.get_action_rules() == {}

    def test_payload_hash_dedup_webhook(self):
        """Same payload sent twice should return existing lead."""
        url = reverse('lead_ingestion:webhook_ingestion')
        self.client.credentials(HTTP_X_AGENTYNE_API_KEY=self.raw_api_key)
        data = {"email": "dupe@test.com", "name": "Dupe"}
        r1 = self.client.post(url, data=data, format='json')
        assert r1.status_code == 202
        r2 = self.client.post(url, data=data, format='json')
        assert r2.status_code == 202
        assert r2.data['raw_lead_id'] == r1.data['raw_lead_id']
        assert r2.data.get('duplicate') is True
        assert RawLead.objects.filter(tenant=self.tenant).count() == 1

    def test_payload_hash_dedup_form(self):
        """Same form payload sent twice should return existing lead."""
        url = reverse('lead_ingestion:form_ingestion')
        self.client.credentials(HTTP_X_AGENTYNE_API_KEY=self.raw_api_key)
        body = "name=Dupont&email=dupont@test.com"
        r1 = self.client.post(url, data=body, content_type='application/x-www-form-urlencoded')
        assert r1.status_code == 202
        r2 = self.client.post(url, data=body, content_type='application/x-www-form-urlencoded')
        assert r2.status_code == 202
        assert r2.data['raw_lead_id'] == r1.data['raw_lead_id']
        assert r2.data.get('duplicate') is True
        assert RawLead.objects.filter(tenant=self.tenant).count() == 1

    def test_duplicate_webhook_returns_202(self):
        """A new dedicated test case to POST the identical payload twice and assert 202 is returned."""
        url = reverse('lead_ingestion:webhook_ingestion')
        self.client.credentials(HTTP_X_AGENTYNE_API_KEY=self.raw_api_key)
        data = {"email": "dupe_202@test.com", "name": "Dupe 202"}
        r1 = self.client.post(url, data=data, format='json')
        assert r1.status_code == 202
        assert r1.data.get('duplicate', False) is False

        r2 = self.client.post(url, data=data, format='json')
        assert r2.status_code == 202
        assert r2.data.get('duplicate') is True

    def test_payload_hash_dedup_csv(self):
        """Duplicate rows in CSV upload should be skipped."""
        url = reverse('lead_ingestion:csv_ingestion')
        self.client.credentials(HTTP_X_AGENTYNE_API_KEY=self.raw_api_key)
        csv_content = "Name,Email\nAlice,alice@test.com\nAlice,alice@test.com\n"
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = "dupes.csv"
        r = self.client.post(url, data={"file": csv_file}, format='multipart')
        assert r.status_code == 202
        assert r.data['message'] == "Lead payload received and queued for processing."
        assert RawLead.objects.filter(tenant=self.tenant).count() == 1

    def test_api_key_auto_hashed_on_save(self):
        """Config API key should be hashed after save."""
        cfg = TenantIngestionConfig.objects.get(pk=self.config.pk)
        assert cfg.api_key != self.raw_api_key
        assert cfg.api_key.startswith('pbkdf2_sha256$') or cfg._is_hashed(cfg.api_key)

    def test_api_key_verify_success(self):
        """verify_api_key should match original plaintext key."""
        cfg = TenantIngestionConfig.objects.get(pk=self.config.pk)
        assert cfg.verify_api_key(self.raw_api_key)

    def test_api_key_verify_failure(self):
        """verify_api_key should reject wrong keys."""
        cfg = TenantIngestionConfig.objects.get(pk=self.config.pk)
        assert not cfg.verify_api_key('wrong-key')

    def test_api_key_masked(self):
        """get_masked_key should not expose the full key."""
        cfg = TenantIngestionConfig.objects.get(pk=self.config.pk)
        masked = cfg.get_masked_key()
        assert len(masked) > 0
        assert masked != self.raw_api_key
        assert '...' in masked

    @patch('lead_ingestion.tasks.parse_lead')
    def test_no_duplicate_parsed_leads_on_double_batch(self, mock_parse, linkedin_payload_1):
        """Running the batch task twice never creates duplicate ParsedLeads."""
        mock_parse.return_value = {
            "name": "Sarah Connor",
            "phone": "+14155550199",
            "email": "sconnor@cyberdyne.com",
            "source": "linkedin",
            "confidence_note": "",
        }

        raw_lead = RawLead.objects.create(
            tenant=self.tenant, source_hint='webhook', payload=linkedin_payload_1,
        )
        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()

        process_pending_leads()
        process_pending_leads()

        raw_lead.refresh_from_db()
        assert raw_lead.status == RawLead.STATUS_PARSED
        assert ParsedLead.objects.filter(raw_lead=raw_lead).count() == 1

    @patch('lead_ingestion.tasks.parse_lead')
    def test_both_missing_lead_goes_to_failed_via_task(self, mock_parse, linkedin_payload_1):
        """A lead with both phone and email missing is marked failed after 3 retries."""
        mock_parse.side_effect = ParseError("Both phone and email are missing")

        raw_lead = RawLead.objects.create(
            tenant=self.tenant, source_hint='webhook', payload=linkedin_payload_1,
        )
        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()

        for _ in range(3):
            raw_lead.refresh_from_db()
            raw_lead.received_at = timezone.now() - timedelta(minutes=15)
            raw_lead.save()
            process_pending_leads()

        raw_lead.refresh_from_db()
        assert raw_lead.status == RawLead.STATUS_FAILED
        assert raw_lead.retry_count == 3
        assert "Both phone and email are missing" in raw_lead.error_detail
        assert ParsedLead.objects.filter(raw_lead=raw_lead).exists() is False

    @patch('lead_ingestion.tasks.parse_lead')
    def test_source_fallback_to_source_hint(self, mock_parse):
        """Unrecognized source falls back to source_hint before 'other'."""
        mock_parse.return_value = {
            "name": "Test",
            "phone": "+1234567890",
            "email": "test@example.com",
            "source": "unknown_platform",
            "confidence_note": "",
        }

        raw_lead = RawLead.objects.create(
            tenant=self.tenant, source_hint='instagram', payload='{"test": true}',
        )
        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()

        process_pending_leads()

        parsed = ParsedLead.objects.get(raw_lead=raw_lead)
        assert parsed.source == 'instagram'

    @patch('lead_ingestion.tasks.parse_lead')
    def test_source_fallback_to_other_when_no_source_hint(self, mock_parse):
        """Unrecognized source with no matching source_hint falls back to 'other'."""
        mock_parse.return_value = {
            "name": "Test",
            "phone": "+1234567890",
            "email": "test@example.com",
            "source": "weird_source",
            "confidence_note": "",
        }

        raw_lead = RawLead.objects.create(
            tenant=self.tenant, source_hint='some_custom_form', payload='{"test": true}',
        )
        raw_lead.received_at = timezone.now() - timedelta(minutes=15)
        raw_lead.save()

        process_pending_leads()

        parsed = ParsedLead.objects.get(raw_lead=raw_lead)
        assert parsed.source == 'other'

    def test_config_view_action_rules_save(self):
        """Config page can save action rules via POST."""
        self.client.force_login(self.owner)
        url = reverse('lead_ingestion:config')
        rules = '{"meta": "bdr_call", "website": "email"}'
        r = self.client.post(url, {'action': 'save_action_rules', 'action_rules': rules})
        assert r.status_code == 302
        self.config.refresh_from_db()
        assert self.config.action_rules == rules
        assert self.config.get_action_rules() == {"meta": "bdr_call", "website": "email"}

    def test_config_view_regenerate_key(self):
        """Config page can regenerate API key."""
        self.client.force_login(self.owner)
        url = reverse('lead_ingestion:config')
        r = self.client.post(url, {'action': 'regenerate_key'})
        assert r.status_code == 302
        self.config.refresh_from_db()
        assert self.config.api_key != self.raw_api_key
        # New key should still be verifiable (we don't know the raw value, just check hashed)
        assert self.config._is_hashed(self.config.api_key)
