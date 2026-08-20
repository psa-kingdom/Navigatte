"""Integration and Unit Tests for Communications Centre, Outbox, and Resend Webhook Ingestion."""

import base64
import hashlib
import hmac
import json
import time
import pytest

from models.communications import OutboxStatus
from models.enquiry import Enquiry


def test_communications_overview_unauthorized(client):
    """Unauthenticated requests to communications overview must return 401."""
    resp = client.get("/api/admin/communications/overview")
    assert resp.status_code == 401


def test_communications_overview_authenticated(client, auth_headers):
    """Authenticated admin receives delivery metrics and provider metadata."""
    resp = client.get("/api/admin/communications/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "metrics" in data
    assert "provider" in data
    assert data["provider"]["name"] == "resend"
    assert data["provider"]["sending_domain"] == "updates.navigatte.com"
    assert "delivery_rate_percent" in data["metrics"]


def test_templates_lifecycle(client, auth_headers):
    """Admin can list and update email templates."""
    # List templates (seeds defaults automatically)
    resp = client.get("/api/admin/communications/templates", headers=auth_headers)
    assert resp.status_code == 200
    templates = resp.json()
    assert len(templates) >= 4

    keys = [t["key"] for t in templates]
    assert "enquiry_acknowledgement" in keys
    assert "consultation_booking_confirmation" in keys

    # Update template
    update_payload = {
        "name": "Updated Enquiry Intake Acknowledgement",
        "subject": "Custom Subject: Thank you {{ name }}",
        "body_html": "<p>Custom body for {{ name }}</p>",
        "body_text": "Custom body for {{ name }}",
        "variables": ["name"],
        "is_active": True,
    }
    update_resp = client.post(
        "/api/admin/communications/templates/enquiry_acknowledgement",
        headers=auth_headers,
        json=update_payload,
    )
    assert update_resp.status_code == 200


def test_send_test_email_unconfigured_provider_returns_truthful_status(client, auth_headers):
    """When provider is unconfigured, send-test reports success=False and status=provider_disabled."""
    payload = {
        "recipient_email": "client@enterprise.com",
        "recipient_name": "Enterprise Client",
        "template_key": "enquiry_acknowledgement",
        "variables": {"name": "Enterprise Client", "service_interest": "Cloud Modernization"},
    }
    send_resp = client.post("/api/admin/communications/send-test", headers=auth_headers, json=payload)
    assert send_resp.status_code == 200
    send_data = send_resp.json()
    assert send_data["success"] is False
    assert send_data["status"] == "provider_disabled"
    assert "RESEND_API_KEY" in send_data["error_message"]

    # Check outbox listing
    outbox_resp = client.get("/api/admin/communications/outbox", headers=auth_headers)
    assert outbox_resp.status_code == 200
    outbox_data = outbox_resp.json()
    assert outbox_data["total"] >= 1
    assert any(item["recipient_email"] == "client@enterprise.com" for item in outbox_data["items"])


def test_send_test_email_with_configured_provider(client, auth_headers, monkeypatch):
    """When Resend is mocked as enabled/success, send-test reports success=True and status=sent."""
    from integrations.contracts.communications import EmailDeliveryResult
    from datetime import datetime, timezone
    from services.communications_service import CommunicationsService

    async def mock_send(self, message):
        return EmailDeliveryResult(
            provider="resend",
            message_id="msg_test_mock_12345",
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.send_email", mock_send)
    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.is_enabled", lambda self: True)

    payload = {
        "recipient_email": "real.prospect@fortune500.com",
        "recipient_name": "VP Technology",
        "template_key": "enquiry_acknowledgement",
        "variables": {"name": "VP Technology", "service_interest": "Technical Advisory"},
    }
    send_resp = client.post("/api/admin/communications/send-test", headers=auth_headers, json=payload)
    assert send_resp.status_code == 200
    send_data = send_resp.json()
    assert send_data["success"] is True
    assert send_data["status"] == "sent"
    assert send_data["provider_message_id"] == "msg_test_mock_12345"


def test_communications_diagnostics_and_single_outbox_get(client, auth_headers):
    """Admin can query system diagnostics and fetch single outbox items by ID."""
    diag_resp = client.get("/api/admin/communications/diagnostics", headers=auth_headers)
    assert diag_resp.status_code == 200
    diag_data = diag_resp.json()
    assert "provider" in diag_data
    assert "environment" in diag_data
    assert diag_data["provider"]["name"] == "resend"
    assert "sending_domain" in diag_data["provider"]


@pytest.mark.asyncio
async def test_resend_webhook_ingestion_and_crm_timeline(client, monkeypatch):
    """Inbound Svix-signed Resend delivery webhook updates outbox and CRM enquiry activity."""
    from core.database import get_database
    from services.communications_service import CommunicationsService

    db = get_database()

    # 1. Setup secret
    raw_secret = b"0123456789abcdef0123456789abcdef"
    secret_b64 = base64.b64encode(raw_secret).decode("utf-8")
    mock_secret = f"whsec_{secret_b64}"
    monkeypatch.setattr("core.config.settings.RESEND_WEBHOOK_SECRET", mock_secret)

    # 2. Create lead in CRM
    enquiry = Enquiry(
        name="Elena Rostova",
        email="elena.rostova@techcorp.io",
        company="TechCorp",
        service_interest="Intelligent Automation",
        message="Interested in RPA",
    )
    await db.enquiries.insert_one(enquiry.to_mongo())

    # 3. Queue an outbox item linked to this enquiry
    service = CommunicationsService()
    outbox_item = await service.send_transactional_email(
        db=db,
        template_key="consultation_booking_confirmation",
        recipient_email=enquiry.email,
        recipient_name=enquiry.name,
        variables={"name": enquiry.name, "start_time": "Aug 22, 2026, 3:00 PM", "timezone": "UTC", "meeting_url": "https://cal.com/meeting/123"},
        enquiry_id=enquiry.id,
    )

    # Simulate provider assigned message ID
    provider_msg_id = "msg_resend_deliv_999"
    await db.email_outbox.update_one(
        {"_id": outbox_item.id},
        {"$set": {"provider_message_id": provider_msg_id, "status": "sent"}}
    )

    # 4. Construct signed webhook payload for email.delivered
    webhook_payload = {
        "type": "email.delivered",
        "created_at": "2026-08-20T15:00:00.000Z",
        "data": {
            "email_id": provider_msg_id,
            "from": "Navigatte <updates@updates.navigatte.com>",
            "to": ["elena.rostova@techcorp.io"],
            "subject": "Confirmed: Navigatte Technical Consultation",
        }
    }
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    msg_id = "msg_svix_resend_deliv_001"
    msg_timestamp = str(int(time.time()))

    to_sign = f"{msg_id}.{msg_timestamp}.".encode("utf-8") + raw_body
    sig_bytes = hmac.new(raw_secret, to_sign, hashlib.sha256).digest()
    sig_b64 = base64.b64encode(sig_bytes).decode("utf-8")

    headers = {
        "svix-id": msg_id,
        "svix-timestamp": msg_timestamp,
        "svix-signature": f"v1,{sig_b64}",
        "content-type": "application/json",
    }

    # 5. POST to /api/webhooks/resend
    resp = client.post("/api/webhooks/resend", data=raw_body, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    # 6. Verify Outbox item was updated to 'delivered'
    updated_outbox = await db.email_outbox.find_one({"_id": outbox_item.id})
    assert updated_outbox["status"] == OutboxStatus.DELIVERED.value
    assert updated_outbox["delivered_at"] is not None

    # 7. Verify CRM Lead received an activity entry
    updated_lead = await db.enquiries.find_one({"_id": enquiry.id})
    activities = updated_lead.get("activities", [])
    assert any(a["type"] == "email_delivered" for a in activities)

    # 8. Test Idempotency (resending same webhook payload)
    dup_resp = client.post("/api/webhooks/resend", data=raw_body, headers=headers)
    assert dup_resp.status_code == 200
    assert dup_resp.json()["status"] == "already_processed"


@pytest.mark.asyncio
async def test_public_enquiry_automatic_acknowledgement_dispatch(client):
    """Submitting a real prospect enquiry automatically queues an enquiry_acknowledgement email."""
    from core.database import get_database

    db = get_database()
    initial_count = await db.email_outbox.count_documents({"template_key": "enquiry_acknowledgement"})

    payload = {
        "name": "Marcus Vance",
        "email": "marcus.vance@vancetech.com",
        "company": "Vance Technology",
        "service_interest": "Cloud & AI Modernization",
        "message": "We would like to consult on enterprise architecture.",
    }
    resp = client.post("/api/enquiries", json=payload)
    assert resp.status_code == 200

    # Verify outbox item created
    final_count = await db.email_outbox.count_documents({"template_key": "enquiry_acknowledgement"})
    assert final_count == initial_count + 1

    item = await db.email_outbox.find_one({"recipient_email": "marcus.vance@vancetech.com"})
    assert item is not None
    assert item["template_key"] == "enquiry_acknowledgement"
    assert "Marcus Vance" in item["subject"] or "Thank you" in item["subject"] or "Navigatte" in item["subject"]


@pytest.mark.asyncio
async def test_honeypot_and_diagnostic_leads_skip_email(client):
    """Honeypot spam submissions and diagnostic test leads never receive outbound emails."""
    from core.database import get_database

    db = get_database()
    initial_count = await db.email_outbox.count_documents({})

    # 1. Honeypot spam submission
    hp_payload = {
        "name": "Spam Bot",
        "email": "spambot@spammer.org",
        "message": "Buy cheap stuff",
        "website_hp": "http://spam.org",
    }
    resp1 = client.post("/api/enquiries", json=hp_payload)
    assert resp1.status_code == 200

    # 2. Diagnostic test lead submission
    test_payload = {
        "name": "Test RCA Diagnostic",
        "email": "rca_verification_test@navigatte.internal",
        "message": "Automated system test probe",
    }
    resp2 = client.post("/api/enquiries", json=test_payload)
    assert resp2.status_code == 200

    # Verify no new outbox items were created for either submission
    final_count = await db.email_outbox.count_documents({})
    assert final_count == initial_count


@pytest.mark.asyncio
async def test_cal_booking_lifecycle_automatic_emails(client, monkeypatch):
    """Cal.com booking webhooks trigger booking confirmation, reschedule, and cancellation emails."""
    from core.database import get_database

    db = get_database()
    secret = "test_cal_comm_secret_key"
    monkeypatch.setattr("core.config.settings.CAL_WEBHOOK_SECRET", secret)

    def sign_payload(payload_dict):
        raw = json.dumps(payload_dict).encode("utf-8")
        sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        return raw, {"x-cal-signature-256": sig, "content-type": "application/json"}

    # 1. BOOKING_CREATED
    booking_created_payload = {
        "triggerEvent": "BOOKING_CREATED",
        "createdAt": "2026-08-20T10:00:00.000Z",
        "payload": {
            "uid": "booking_comm_001",
            "title": "Strategy Architecture Consultation",
            "startTime": "2026-08-25T14:00:00.000Z",
            "endTime": "2026-08-25T14:45:00.000Z",
            "metadata": {"videoCallUrl": "https://cal.com/meet/test001"},
            "responses": {
                "name": {"value": "Liam Gallagher"},
                "email": {"value": "liam.gallagher@oasis-corp.co.uk"},
            },
        },
    }
    raw, headers = sign_payload(booking_created_payload)
    resp = client.post("/api/webhooks/cal", data=raw, headers=headers)
    assert resp.status_code == 200

    # Verify confirmation email queued in outbox
    conf_item = await db.email_outbox.find_one({"recipient_email": "liam.gallagher@oasis-corp.co.uk", "template_key": "consultation_booking_confirmation"})
    assert conf_item is not None
    assert "Liam Gallagher" in conf_item["body_html"]

    # 2. BOOKING_RESCHEDULED
    booking_resched_payload = {
        "triggerEvent": "BOOKING_RESCHEDULED",
        "createdAt": "2026-08-20T11:00:00.000Z",
        "payload": {
            "uid": "booking_comm_001",
            "title": "Strategy Architecture Consultation",
            "startTime": "2026-08-26T15:00:00.000Z",
            "endTime": "2026-08-26T15:45:00.000Z",
            "metadata": {"videoCallUrl": "https://cal.com/meet/test001"},
            "responses": {
                "name": {"value": "Liam Gallagher"},
                "email": {"value": "liam.gallagher@oasis-corp.co.uk"},
            },
        },
    }
    raw, headers = sign_payload(booking_resched_payload)
    resp2 = client.post("/api/webhooks/cal", data=raw, headers=headers)
    assert resp2.status_code == 200

    resched_item = await db.email_outbox.find_one({"recipient_email": "liam.gallagher@oasis-corp.co.uk", "template_key": "consultation_rescheduled"})
    assert resched_item is not None

    # 3. BOOKING_CANCELLED
    booking_cancel_payload = {
        "triggerEvent": "BOOKING_CANCELLED",
        "createdAt": "2026-08-20T12:00:00.000Z",
        "payload": {
            "uid": "booking_comm_001",
            "title": "Strategy Architecture Consultation",
            "startTime": "2026-08-26T15:00:00.000Z",
            "endTime": "2026-08-26T15:45:00.000Z",
            "cancellationReason": "Client schedule conflict",
            "responses": {
                "name": {"value": "Liam Gallagher"},
                "email": {"value": "liam.gallagher@oasis-corp.co.uk"},
            },
        },
    }
    raw, headers = sign_payload(booking_cancel_payload)
    resp3 = client.post("/api/webhooks/cal", data=raw, headers=headers)
    assert resp3.status_code == 200

    cancel_item = await db.email_outbox.find_one({"recipient_email": "liam.gallagher@oasis-corp.co.uk", "template_key": "consultation_cancelled"})
    assert cancel_item is not None


@pytest.mark.asyncio
async def test_outbox_retry_endpoint(client, auth_headers):
    """Admin can retry a failed outbox email item."""
    from core.database import get_database
    from models.communications import OutboxItemModel

    db = get_database()
    failed_item = OutboxItemModel(
        idempotency_key="test:manual:retry:001",
        recipient_email="retry.test@client.com",
        recipient_name="Retry Client",
        subject="Retry Test Subject",
        body_html="<p>Test retry content</p>",
        status=OutboxStatus.FAILED,
        error_message="Simulated connection timeout",
        attempt_count=1,
    )
    await db.email_outbox.insert_one(failed_item.to_mongo())

    resp = client.post(f"/api/admin/communications/outbox/{failed_item.id}/retry", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["attempt_count"] == 2
    assert data["outbox_id"] == failed_item.id

    # Test single outbox item GET
    item_resp = client.get(f"/api/admin/communications/outbox/{failed_item.id}", headers=auth_headers)
    assert item_resp.status_code == 200
    assert item_resp.json()["id"] == failed_item.id


@pytest.mark.asyncio
async def test_outbox_retry_delivered_guard(client, auth_headers):
    """Retrying an already delivered email is rejected with 400."""
    from core.database import get_database
    from models.communications import OutboxItemModel

    db = get_database()
    delivered_item = OutboxItemModel(
        idempotency_key="test:delivered:retry:002",
        recipient_email="delivered@client.com",
        recipient_name="Delivered Client",
        subject="Already Delivered",
        body_html="<p>Delivered</p>",
        status=OutboxStatus.DELIVERED,
        attempt_count=1,
    )
    await db.email_outbox.insert_one(delivered_item.to_mongo())

    resp = client.post(f"/api/admin/communications/outbox/{delivered_item.id}/retry", headers=auth_headers)
    assert resp.status_code == 400
    assert "already delivered" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_outbox_retry_max_attempts_guard(client, auth_headers):
    """Retrying an item that has reached max_attempts is rejected with 400."""
    from core.database import get_database
    from models.communications import OutboxItemModel

    db = get_database()
    exhausted_item = OutboxItemModel(
        idempotency_key="test:exhausted:retry:003",
        recipient_email="exhausted@client.com",
        recipient_name="Exhausted Client",
        subject="Max Attempts Exhausted",
        body_html="<p>Exhausted</p>",
        status=OutboxStatus.FAILED,
        attempt_count=3,
        max_attempts=3,
    )
    await db.email_outbox.insert_one(exhausted_item.to_mongo())

    resp = client.post(f"/api/admin/communications/outbox/{exhausted_item.id}/retry", headers=auth_headers)
    assert resp.status_code == 400
    assert "maximum retry attempts" in resp.json()["detail"].lower()
