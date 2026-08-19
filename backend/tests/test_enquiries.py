"""Tests for Enquiries and CRM domain."""

import pytest
from core.database import get_database


def test_public_enquiry_submission_success(client):
    payload = {
        "name": "Sarah Jenkins",
        "email": "sarah@acmecorp.com",
        "company": "Acme Corp",
        "phone": "+1 555 123 4567",
        "service_interest": "enterprise-applications",
        "message": "We would like to consult on modernizing our ERP pipeline.",
    }
    resp = client.post("/api/enquiries", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "Thank you" in data["message"]


def test_public_enquiry_validation_errors(client):
    # Invalid email
    resp1 = client.post("/api/enquiries", json={"name": "Bob", "email": "not-an-email", "message": "Valid message here"})
    assert resp1.status_code == 422

    # Message too short
    resp2 = client.post("/api/enquiries", json={"name": "Bob", "email": "bob@example.com", "message": "Hi"})
    assert resp2.status_code == 422

    # Name too short
    resp3 = client.post("/api/enquiries", json={"name": "B", "email": "bob@example.com", "message": "Valid message here"})
    assert resp3.status_code == 422


def test_honeypot_bot_protection(client):
    """Spam bots filling the honeypot field should receive a 200 success response but not be stored."""
    import asyncio
    db = get_database()

    bot_email = "spambot_test_hp@badactor.com"

    # Ensure clean slate for this email
    async def _clean():
        await db.enquiries.delete_many({"email": bot_email})

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(_clean())

    payload = {
        "name": "Spam Bot",
        "email": bot_email,
        "message": "Buy cheap stuff now!",
        "website_hp": "http://spam-link.com",  # Honeypot filled!
    }
    resp = client.post("/api/enquiries", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify NOT stored in database
    async def _check():
        return await db.enquiries.find_one({"email": bot_email})

    doc = loop.run_until_complete(_check())
    assert doc is None, "Honeypot-triggered enquiry must not be inserted into the database!"


def test_admin_enquiries_unauthorized(client):
    resp = client.get("/api/admin/enquiries")
    assert resp.status_code == 401


def test_admin_enquiry_lifecycle_and_notes(client, auth_headers):
    # 1. Submit a real enquiry
    lead_email = "lead_pipeline_test@enterprise.com"
    client.post("/api/enquiries", json={
        "name": "David Miller",
        "email": lead_email,
        "company": "Apex Dynamics",
        "message": "We need AI automation for document processing.",
    })

    # 2. Admin retrieves list and searches by company
    list_resp = client.get("/api/admin/enquiries", params={"search": "Apex Dynamics"}, headers=auth_headers)
    assert list_resp.status_code == 200
    leads = list_resp.json()
    assert len(leads) >= 1
    lead = leads[0]
    lead_id = lead["id"]
    assert lead["status"] == "new"
    assert lead["email"] == lead_email

    # 3. Admin gets single enquiry
    get_resp = client.get(f"/api/admin/enquiries/{lead_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == lead_id

    # 4. Admin advances status in CRM pipeline: new -> contacted
    status_resp = client.patch(
        f"/api/admin/enquiries/{lead_id}/status",
        json={"status": "contacted"},
        headers=auth_headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "contacted"

    # 5. Admin appends an internal note
    note_resp = client.post(
        f"/api/admin/enquiries/{lead_id}/notes",
        json={"text": "Called David; scheduled a 30-min discovery call for next Tuesday."},
        headers=auth_headers,
    )
    assert note_resp.status_code == 200
    updated_lead = note_resp.json()
    assert len(updated_lead["notes"]) == 1
    assert "scheduled a 30-min discovery" in updated_lead["notes"][0]["text"]
    assert "created_by" in updated_lead["notes"][0]
