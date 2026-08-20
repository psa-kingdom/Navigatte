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


def test_send_test_email_and_outbox_listing(client, auth_headers):
    """Admin can dispatch a test email and view it in the outbox."""
    payload = {
        "recipient_email": "client@enterprise.com",
        "recipient_name": "Enterprise Client",
        "template_key": "enquiry_acknowledgement",
        "variables": {"name": "Enterprise Client", "service_interest": "Cloud Modernization"},
    }
    send_resp = client.post("/api/admin/communications/send-test", headers=auth_headers, json=payload)
    assert send_resp.status_code == 200
    send_data = send_resp.json()
    assert send_data["success"] is True

    # Check outbox listing
    outbox_resp = client.get("/api/admin/communications/outbox", headers=auth_headers)
    assert outbox_resp.status_code == 200
    outbox_data = outbox_resp.json()
    assert outbox_data["total"] >= 1
    assert any(item["recipient_email"] == "client@enterprise.com" for item in outbox_data["items"])


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
