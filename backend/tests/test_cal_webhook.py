"""Comprehensive test suite for Cal.com webhook ingestion, signature verification,
idempotency, attendee matching, and CRM activity timeline.
"""

import asyncio
import hashlib
import hmac
import json
import pytest
from core.database import get_database
from core.config import settings
from models.enquiry import Enquiry, EnquiryStatus, SchedulingStatus

SECRET = "test_webhook_signing_secret_998877"


def generate_signature(body_bytes: bytes, secret: str = SECRET) -> str:
    """Generates valid HMAC-SHA256 signature hex for testing."""
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=body_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()


@pytest.fixture(autouse=True)
def override_cal_config(monkeypatch):
    """Configures Cal.com settings for unit testing."""
    monkeypatch.setattr(settings, "CAL_ENABLED", True)
    monkeypatch.setattr(settings, "CAL_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(settings, "_raw_jwt_secret", "test_jwt_secret_123456789")


def test_cal_webhook_missing_signature(client):
    payload = {"triggerEvent": "BOOKING_CREATED", "payload": {"uid": "bkg_001"}}
    resp = client.post("/api/webhooks/cal", json=payload)
    assert resp.status_code == 401
    assert "signature" in resp.json()["detail"].lower()


def test_cal_webhook_invalid_signature(client):
    body_bytes = json.dumps({"triggerEvent": "BOOKING_CREATED", "payload": {"uid": "bkg_001"}}).encode()
    resp = client.post(
        "/api/webhooks/cal",
        content=body_bytes,
        headers={"x-cal-signature-256": "invalid_hex_signature_123456", "content-type": "application/json"},
    )
    assert resp.status_code == 401


def test_cal_webhook_malformed_json(client):
    body_bytes = b"not-a-valid-json-string"
    sig = generate_signature(body_bytes)
    resp = client.post(
        "/api/webhooks/cal",
        content=body_bytes,
        headers={"x-cal-signature-256": sig, "content-type": "application/json"},
    )
    assert resp.status_code == 400


def test_booking_created_matches_existing_lead(client):
    db = get_database()
    email = "alex.mercer@prototype.com"

    # 1. Seed an existing contact form lead
    async def _setup():
        await db.enquiries.delete_many({"email": {"$regex": "alex.mercer@", "$options": "i"}})
        existing_enquiry = Enquiry(
            name="Alex Mercer",
            email=email,
            company="Gentek Corp",
            message="Interested in cloud modernization",
            status=EnquiryStatus.NEW,
        )
        insert_res = await db.enquiries.insert_one(existing_enquiry.to_mongo())
        return insert_res.upserted_id or existing_enquiry.id

    lead_id = asyncio.run(_setup())

    # 2. Receive Cal.com BOOKING_CREATED payload
    webhook_payload = {
        "triggerEvent": "BOOKING_CREATED",
        "createdAt": "2026-08-20T10:00:00.000Z",
        "payload": {
            "uid": "bkg_alex_001",
            "title": "Platform Architecture Consultation",
            "startTime": "2026-08-25T14:00:00Z",
            "endTime": "2026-08-25T14:30:00Z",
            "timeZone": "America/New_York",
            "meetingUrl": "https://meet.google.com/nav-test-abc",
            "attendees": [
                {
                    "name": "Alex Mercer",
                    "email": "Alex.Mercer@prototype.com",  # Mixed case to test case-insensitive matching
                    "phoneNumber": "+1-555-0199",
                }
            ],
            "type": "strategy-session",
        },
    }

    body_bytes = json.dumps(webhook_payload).encode("utf-8")
    sig = generate_signature(body_bytes)

    resp = client.post(
        "/api/webhooks/cal",
        content=body_bytes,
        headers={"x-cal-signature-256": sig, "content-type": "application/json"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["status"] == "processed"

    # 3. Verify Lead in DB
    async def _verify():
        return await db.enquiries.find_one({"_id": lead_id})

    updated_doc = asyncio.run(_verify())
    assert updated_doc is not None
    assert updated_doc["scheduling_status"] == SchedulingStatus.BOOKED.value
    assert updated_doc["status"] == EnquiryStatus.CONTACTED.value  # advanced from NEW
    assert updated_doc["phone"] == "+1-555-0199"  # enriched phone
    assert updated_doc["booking"]["booking_uid"] == "bkg_alex_001"
    assert updated_doc["booking"]["meeting_url"] == "https://meet.google.com/nav-test-abc"
    assert len(updated_doc["activities"]) == 1
    assert updated_doc["activities"][0]["type"] == "booking_created"


def test_booking_created_creates_new_lead(client):
    db = get_database()
    email = "sarah.connor@cyberdyne.org"

    async def _cleanup():
        await db.enquiries.delete_many({"email": email})
        await db.integration_webhook_events.delete_many({"external_booking_uid": "bkg_sarah_002"})

    asyncio.run(_cleanup())

    webhook_payload = {
        "triggerEvent": "BOOKING_CREATED",
        "createdAt": "2026-08-20T11:00:00.000Z",
        "payload": {
            "uid": "bkg_sarah_002",
            "title": "Discovery Call",
            "startTime": "2026-08-26T15:00:00Z",
            "endTime": "2026-08-26T15:30:00Z",
            "timeZone": "Europe/London",
            "meetingUrl": "https://meet.google.com/nav-sarah-123",
            "attendees": [
                {
                    "name": "Sarah Connor",
                    "email": email,
                    "phoneNumber": "+44-20-7946-0912",
                }
            ],
            "type": "discovery",
            "description": "Discussing resilient automation workflows",
        },
    }

    body_bytes = json.dumps(webhook_payload).encode("utf-8")
    sig = generate_signature(body_bytes)

    resp = client.post(
        "/api/webhooks/cal",
        content=body_bytes,
        headers={"x-cal-signature-256": sig, "content-type": "application/json"},
    )

    assert resp.status_code == 200

    async def _check():
        return await db.enquiries.find_one({"email": email})

    created_lead = asyncio.run(_check())
    assert created_lead is not None
    assert created_lead["name"] == "Sarah Connor"
    assert created_lead["source"] == "cal.com"
    assert created_lead["scheduling_status"] == SchedulingStatus.BOOKED.value
    assert len(created_lead["activities"]) == 2  # enquiry_submitted + booking_created


def test_booking_rescheduled_and_cancelled_lifecycle(client):
    db = get_database()
    email = "david.hassel@knight.io"
    booking_uid = "bkg_david_003"

    async def _cleanup():
        await db.enquiries.delete_many({"email": email})
        await db.integration_webhook_events.delete_many({"external_booking_uid": booking_uid})

    asyncio.run(_cleanup())

    # Step 1: Initial Booking
    create_payload = {
        "triggerEvent": "BOOKING_CREATED",
        "createdAt": "2026-08-20T12:00:00.000Z",
        "payload": {
            "uid": booking_uid,
            "title": "Initial Call",
            "startTime": "2026-08-27T10:00:00Z",
            "attendees": [{"name": "David Hassel", "email": email}],
        },
    }
    body1 = json.dumps(create_payload).encode()
    resp1 = client.post("/api/webhooks/cal", content=body1, headers={"x-cal-signature-256": generate_signature(body1)})
    assert resp1.status_code == 200

    # Step 2: Reschedule Event
    reschedule_payload = {
        "triggerEvent": "BOOKING_RESCHEDULED",
        "createdAt": "2026-08-20T13:00:00.000Z",
        "payload": {
            "uid": booking_uid,
            "title": "Initial Call (Rescheduled)",
            "startTime": "2026-08-29T16:00:00Z",
            "attendees": [{"name": "David Hassel", "email": email}],
        },
    }
    body2 = json.dumps(reschedule_payload).encode()
    resp2 = client.post("/api/webhooks/cal", content=body2, headers={"x-cal-signature-256": generate_signature(body2)})
    assert resp2.status_code == 200

    async def _check_rescheduled():
        return await db.enquiries.find_one({"email": email})

    lead = asyncio.run(_check_rescheduled())
    assert lead["scheduling_status"] == SchedulingStatus.RESCHEDULED.value
    assert any(a["type"] == "booking_rescheduled" for a in lead["activities"])

    # Step 3: Cancellation Event
    cancel_payload = {
        "triggerEvent": "BOOKING_CANCELLED",
        "createdAt": "2026-08-20T14:00:00.000Z",
        "payload": {
            "uid": booking_uid,
            "cancellationReason": "Client conflict with board meeting",
            "attendees": [{"name": "David Hassel", "email": email}],
        },
    }
    body3 = json.dumps(cancel_payload).encode()
    resp3 = client.post("/api/webhooks/cal", content=body3, headers={"x-cal-signature-256": generate_signature(body3)})
    assert resp3.status_code == 200

    async def _check_cancelled():
        return await db.enquiries.find_one({"email": email})

    lead_cancelled = asyncio.run(_check_cancelled())
    assert lead_cancelled["scheduling_status"] == SchedulingStatus.CANCELLED.value
    cancel_activity = next(a for a in lead_cancelled["activities"] if a["type"] == "booking_cancelled")
    assert "board meeting" in cancel_activity["summary"]


def test_webhook_idempotency_duplicate_prevented(client):
    db = get_database()
    email = "repeat@example.com"
    booking_uid = "bkg_idempotency_test"

    async def _cleanup():
        await db.enquiries.delete_many({"email": email})
        await db.integration_webhook_events.delete_many({"external_booking_uid": booking_uid})

    asyncio.run(_cleanup())

    payload = {
        "triggerEvent": "BOOKING_CREATED",
        "createdAt": "2026-08-20T15:00:00.000Z",
        "payload": {
            "uid": booking_uid,
            "title": "Idempotency Test Meeting",
            "startTime": "2026-09-01T10:00:00Z",
            "attendees": [{"name": "Repeated Attendee", "email": email}],
        },
    }
    body = json.dumps(payload).encode()
    sig = generate_signature(body)
    headers = {"x-cal-signature-256": sig, "content-type": "application/json"}

    # Delivery 1: Processed
    resp1 = client.post("/api/webhooks/cal", content=body, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "processed"

    # Delivery 2 (Retry): Duplicate
    resp2 = client.post("/api/webhooks/cal", content=body, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"

    # Delivery 3 (Retry): Duplicate
    resp3 = client.post("/api/webhooks/cal", content=body, headers=headers)
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "duplicate"

    # Assert exactly 1 enquiry exists in DB
    async def _count():
        cursor = db.enquiries.find({"email": email})
        return await cursor.to_list(10)

    docs = asyncio.run(_count())
    assert len(docs) == 1


def test_rca_diagnostic_lead_excluded_from_business_stats():
    from routers.enquiries import _resolve_stats
    db = get_database()

    async def _run():
        await db.enquiries.delete_many({})

        # Real Customer Enquiry
        real_lead = Enquiry(
            name="Real Enterprise Prospect",
            email="client@enterprise.com",
            message="Need platform consultation",
            status=EnquiryStatus.NEW,
            is_test=False,
        )
        await db.enquiries.insert_one(real_lead.to_mongo())

        # RCA Diagnostic Test Lead
        test_lead = Enquiry(
            name="Test RCA Verification Lead",
            email="rca_verification_test@navigatte.com",
            message="Automated RCA verification enquiry",
            status=EnquiryStatus.NEW,
            is_test=True,
        )
        await db.enquiries.insert_one(test_lead.to_mongo())

        enquiries_new, enquiries_pipeline, _, _ = await _resolve_stats(db, [EnquiryStatus.CONTACTED.value])
        return enquiries_new, enquiries_pipeline

    enquiries_new, enquiries_pipeline = asyncio.run(_run())
    # Should count ONLY the 1 real lead, strictly excluding the test lead
    assert enquiries_new == 1
    assert enquiries_pipeline == 0


def test_admin_integrations_status(client, auth_headers):
    resp = client.get("/api/admin/integrations/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "cal" in data
    assert data["cal"]["name"] == "Cal.com"
    assert "has_webhook_secret" in data["cal"]
    assert "stats" in data
