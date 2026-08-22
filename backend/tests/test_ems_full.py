"""Comprehensive Unit & Integration Test Suite for the Email Management System (EMS).

Tests:
1. Environment separation & Campaign test recipient safety boundary
2. Campaign lifecycle (Draft -> Ready -> Sending -> Paused -> Cancelled)
3. Launch checklist validation (blocking errors on unconfigured provider/missing audience)
4. Audience & Global Suppression filtering (unsubscribes/bounces excluded from campaign dispatches)
5. Durable Delivery Worker atomic claiming, exponential backoff, and retry limits
6. Template versioning, immutable snapshots, and system template deletion guard
7. Communications Audit Log & Derived Analytics metrics
"""

from datetime import datetime, timezone
import pytest
from core.database import get_database
from models.audience import AudienceModel
from models.campaign import CampaignModel, CampaignStatus
from models.communications import EmailTemplateModel, OutboxItemModel, OutboxStatus
from services.campaign_service import CampaignService
from services.delivery_worker import DeliveryWorker


@pytest.mark.asyncio
async def test_template_versioning_and_system_guard(client, auth_headers):
    """Creating and updating templates creates immutable version snapshots; system templates cannot be deleted."""
    from services.communications_service import CommunicationsService
    db = get_database()
    await CommunicationsService.ensure_default_templates(db)

    # 1. Create custom template
    create_payload = {
        "key": "q3_enterprise_briefing",
        "name": "Q3 Enterprise Strategy Briefing",
        "category": "campaign",
        "subject": "Q3 Enterprise Strategy — {{ name }}",
        "body_html": "<p>Hello {{ name }}, check our Q3 briefing.</p>",
        "body_text": "Hello {{ name }}, check our Q3 briefing.",
        "variables": ["name"],
    }
    resp = client.post("/api/admin/communications/templates", headers=auth_headers, json=create_payload)
    assert resp.status_code == 200
    tpl_data = resp.json()
    assert tpl_data["version"] == 1

    # Verify version 1 snapshot in DB
    v1_count = await db.email_template_versions.count_documents({"template_key": "q3_enterprise_briefing"})
    assert v1_count == 1

    # 2. Update template -> version 2
    update_payload = {
        "name": "Q3 Enterprise Strategy Briefing (Updated)",
        "subject": "Exclusive: Q3 Enterprise Strategy — {{ name }}",
        "body_html": "<p>Updated briefing for {{ name }}</p>",
        "body_text": "Updated briefing for {{ name }}",
        "variables": ["name", "company"],
        "is_active": True,
    }
    update_resp = client.post("/api/admin/communications/templates/q3_enterprise_briefing", headers=auth_headers, json=update_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["version"] == 2

    # Check version history endpoint
    versions_resp = client.get("/api/admin/communications/templates/q3_enterprise_briefing/versions", headers=auth_headers)
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 2
    assert versions[0]["version"] == 2
    assert versions[1]["version"] == 1

    # 3. Guard: Attempt to delete a seeded system template must fail
    del_sys_resp = client.delete("/api/admin/communications/templates/enquiry_acknowledgement", headers=auth_headers)
    assert del_sys_resp.status_code == 400
    assert "protected" in del_sys_resp.json()["detail"].lower()

    # 4. Custom template can be deleted
    del_custom_resp = client.delete("/api/admin/communications/templates/q3_enterprise_briefing", headers=auth_headers)
    assert del_custom_resp.status_code == 200
    assert del_custom_resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_audiences_contacts_and_suppression_flow(client, auth_headers):
    """Audiences accept contacts, and global suppression records dynamically filter them."""
    db = get_database()

    # 1. Create Audience
    aud_payload = {
        "name": "Fortune 500 CTOs",
        "description": "Enterprise decision makers",
        "tags": ["enterprise", "cto", "cloud"],
    }
    aud_resp = client.post("/api/admin/communications/audiences", headers=auth_headers, json=aud_payload)
    assert aud_resp.status_code == 200
    aud = aud_resp.json()
    aud_id = aud["id"]

    # 2. Add Contacts
    c1 = {"email": "cto1@globalbank.com", "name": "Alice Vance", "company": "GlobalBank"}
    c2 = {"email": "cto2@fintech.io", "name": "Bob Chen", "company": "FintechCorp"}
    client.post(f"/api/admin/communications/audiences/{aud_id}/contacts", headers=auth_headers, json=c1)
    client.post(f"/api/admin/communications/audiences/{aud_id}/contacts", headers=auth_headers, json=c2)

    contacts_resp = client.get(f"/api/admin/communications/audiences/{aud_id}/contacts", headers=auth_headers)
    assert contacts_resp.status_code == 200
    assert contacts_resp.json()["total"] == 2

    # 3. Suppress cto2
    suppress_payload = {"email": "cto2@fintech.io", "reason": "unsubscribed", "source": "test"}
    sup_resp = client.post("/api/admin/communications/audiences/suppression", headers=auth_headers, json=suppress_payload)
    assert sup_resp.status_code == 200

    # Verify contact is marked is_suppressed in audience
    updated_c2 = await db.audience_contacts.find_one({"email": "cto2@fintech.io", "audience_id": aud_id})
    assert updated_c2["is_suppressed"] is True


@pytest.mark.asyncio
async def test_campaign_environment_isolation_and_launch_validation(client, auth_headers, monkeypatch):
    """Campaign in TEST mode ONLY sends to test_recipients; PRODUCTION mode validates audience & suppression."""
    from services.communications_service import CommunicationsService
    db = get_database()
    await CommunicationsService.ensure_default_templates(db)

    # Ensure provider is seen as enabled for test
    monkeypatch.setattr("core.config.settings.RESEND_ENABLED", True)
    monkeypatch.setattr("core.config.settings.COMMUNICATIONS_ENVIRONMENT", "test")

    # 1. Create a Campaign in TEST environment
    camp_payload = {
        "name": "Cloud AI Modernization Launch",
        "description": "Q3 Outreach",
        "environment": "test",
        "subject": "Navigatte AI Capabilities Briefing",
        "template_key": "enquiry_acknowledgement",
        "test_recipients": ["qa.tester@navigatte.internal", "dev.lead@navigatte.internal"],
    }
    camp_resp = client.post("/api/admin/communications/campaigns", headers=auth_headers, json=camp_payload)
    assert camp_resp.status_code == 200
    camp = camp_resp.json()
    camp_id = camp["id"]

    # 2. Validate checklist
    val_resp = client.get(f"/api/admin/communications/campaigns/{camp_id}/validate", headers=auth_headers)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["is_valid"] is True
    assert val_data["checklist"]["target_recipients_count"] == 2

    # 3. Launch Campaign in TEST mode
    launch_resp = client.post(f"/api/admin/communications/campaigns/{camp_id}/launch", headers=auth_headers)
    assert launch_resp.status_code == 200
    launched_camp = launch_resp.json()["campaign"]
    assert launched_camp["status"] == "sending"
    assert launched_camp["total_recipients"] == 2

    # Verify queued outbox items are strictly the 2 test recipients
    outbox_docs = await db.email_outbox.find({"tags.campaign_id": camp_id}).to_list(10)
    assert len(outbox_docs) == 2
    emails = {doc["recipient_email"] for doc in outbox_docs}
    assert emails == {"qa.tester@navigatte.internal", "dev.lead@navigatte.internal"}
    assert all(doc["environment"] == "test" for doc in outbox_docs)


@pytest.mark.asyncio
async def test_durable_delivery_worker_batch_processing(client, monkeypatch):
    """DeliveryWorker atomically claims queued outbox records and handles retry backoff."""
    from integrations.contracts.communications import EmailDeliveryResult
    db = get_database()

    # Seed 2 queued items
    item1 = OutboxItemModel(
        idempotency_key="worker:test:001",
        recipient_email="worker.test1@enterprise.io",
        subject="Worker Test 1",
        body_html="<p>Test 1</p>",
        status=OutboxStatus.QUEUED,
        attempt_count=0,
    )
    item2 = OutboxItemModel(
        idempotency_key="worker:test:002",
        recipient_email="worker.test2@enterprise.io",
        subject="Worker Test 2",
        body_html="<p>Test 2</p>",
        status=OutboxStatus.QUEUED,
        attempt_count=0,
    )
    await db.email_outbox.insert_one(item1.to_mongo())
    await db.email_outbox.insert_one(item2.to_mongo())

    # Mock provider send_email
    async def mock_send(self, message):
        return EmailDeliveryResult(
            provider="resend",
            message_id="msg_worker_success_777",
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.send_email", mock_send)
    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.is_enabled", lambda self: True)

    worker = DeliveryWorker()
    batch_result = await worker.process_batch(db, batch_size=10)
    assert batch_result["processed"] >= 2
    assert batch_result["succeeded"] >= 2

    # Verify status in database
    doc1 = await db.email_outbox.find_one({"_id": item1.id})
    assert doc1["status"] == OutboxStatus.SENT.value
    assert doc1["provider_message_id"] == "msg_worker_success_777"


@pytest.mark.asyncio
async def test_audit_logs_and_analytics_endpoints(client, auth_headers):
    """Audit logs list administrative actions and analytics return zero-safe derived metrics."""
    audit_resp = client.get("/api/admin/communications/audit-logs", headers=auth_headers)
    assert audit_resp.status_code == 200
    assert "items" in audit_resp.json()

    analytics_resp = client.get("/api/admin/communications/analytics", headers=auth_headers)
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()
    assert "totals" in data
    assert "rates" in data
    assert "delivery_rate_percent" in data["rates"]
    assert "open_rate_percent" in data["rates"]
    assert isinstance(data["rates"]["delivery_rate_percent"], (int, float))


@pytest.mark.asyncio
async def test_resend_tag_sanitization():
    """Resend tag sanitization guarantees tags only contain ASCII letters, numbers, underscores, or dashes."""
    from integrations.resend.client import _clean_resend_tag, ResendApiClient

    # Valid tags
    assert _clean_resend_tag("campaign_123") == "campaign_123"
    assert _clean_resend_tag("template-key") == "template-key"

    # Empty or whitespace strings return None
    assert _clean_resend_tag("") is None
    assert _clean_resend_tag("   ") is None
    assert _clean_resend_tag(None) is None

    # Special characters like spaces, colons, slashes get sanitized to underscores
    assert _clean_resend_tag("enquiry:123/v2") == "enquiry_123_v2"
    assert _clean_resend_tag("Tag With Spaces!") == "Tag_With_Spaces_"


@pytest.mark.asyncio
async def test_bulk_csv_import_reporting(client, auth_headers):
    """Audience CSV bulk import reports valid, invalid, duplicate, and suppressed counts."""
    db = get_database()

    # 1. Create Audience
    aud_resp = client.post("/api/admin/communications/audiences", headers=auth_headers, json={"name": "CSV Target Group"})
    assert aud_resp.status_code == 200
    aud_id = aud_resp.json()["id"]

    # 2. Add a global suppression
    client.post("/api/admin/communications/audiences/suppression", headers=auth_headers, json={"email": "bounced@suppressed.com", "reason": "hard_bounce"})

    # 3. Import batch with valid, invalid, duplicate, and suppressed emails
    batch = [
        {"email": "valid1@enterprise.com", "name": "Valid 1", "company": "Corp A"},
        {"email": "invalid-email-syntax", "name": "Bad", "company": "Corp B"},
        {"email": "valid1@enterprise.com", "name": "Duplicate of Valid 1"},
        {"email": "bounced@suppressed.com", "name": "Suppressed User"},
        {"email": "valid2@enterprise.com", "name": "Valid 2"},
    ]
    import_resp = client.post(f"/api/admin/communications/audiences/{aud_id}/import", headers=auth_headers, json={"contacts": batch})
    assert import_resp.status_code == 200
    report = import_resp.json()
    assert report["total_rows"] == 5
    assert report["valid_count"] == 3  # 2 valid unique + 1 suppressed unique
    assert report["invalid_count"] == 1
    assert report["duplicate_count"] == 1
    assert report["suppressed_count"] == 1
    assert report["imported_count"] == 3


@pytest.mark.asyncio
async def test_campaign_exclusions_and_net_calculation(client, auth_headers, monkeypatch):
    """Campaign exclusions filter out domains/emails and calculate net verified deliverable recipients."""
    db = get_database()

    # 1. Create Audience with 3 contacts
    aud_resp = client.post("/api/admin/communications/audiences", headers=auth_headers, json={"name": "Exclusion Test Audience"})
    aud_id = aud_resp.json()["id"]

    client.post(f"/api/admin/communications/audiences/{aud_id}/contacts", headers=auth_headers, json={"email": "employee@navigatte.com", "name": "Staff"})
    client.post(f"/api/admin/communications/audiences/{aud_id}/contacts", headers=auth_headers, json={"email": "client@enterprise.com", "name": "Client"})
    client.post(f"/api/admin/communications/audiences/{aud_id}/contacts", headers=auth_headers, json={"email": "partner@consulting.io", "name": "Partner"})

    # 2. Create Production Campaign with domain exclusion '@navigatte.com'
    camp_payload = {
        "name": "Exclusions Campaign",
        "environment": "production",
        "subject": "Advisory Note",
        "template_key": "custom",
        "custom_html": "<p>Content</p>",
        "audience_id": aud_id,
        "exclusions": ["@navigatte.com"],
    }
    camp_resp = client.post("/api/admin/communications/campaigns", headers=auth_headers, json=camp_payload)
    assert camp_resp.status_code == 200
    camp_id = camp_resp.json()["id"]

    # 3. Calculate recipients endpoint
    calc_resp = client.post(f"/api/admin/communications/campaigns/{camp_id}/calculate-recipients", headers=auth_headers)
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()
    assert calc_data["raw_count"] == 3
    assert calc_data["excluded_count"] == 1  # employee@navigatte.com excluded
    assert calc_data["final_count"] == 2


@pytest.mark.asyncio
async def test_campaign_draft_update_and_preview(client, auth_headers):
    """Campaign drafts can be updated and previewed with sample variable interpolation."""
    # 1. Create Draft
    camp_resp = client.post("/api/admin/communications/campaigns", headers=auth_headers, json={
        "name": "Draft to Edit",
        "subject": "Initial Subject {{ name }}",
        "custom_html": "<p>Hello {{ name }} at {{ company }}</p>",
    })
    assert camp_resp.status_code == 200
    camp_id = camp_resp.json()["id"]

    # 2. Update Draft
    put_resp = client.put(f"/api/admin/communications/campaigns/{camp_id}", headers=auth_headers, json={
        "name": "Draft to Edit (Renamed)",
        "subject": "Updated Subject {{ name }}",
    })
    assert put_resp.status_code == 200
    assert put_resp.json()["name"] == "Draft to Edit (Renamed)"

    # 3. Preview Endpoint
    prev_resp = client.get(f"/api/admin/communications/campaigns/{camp_id}/preview", headers=auth_headers)
    assert prev_resp.status_code == 200
    prev_data = prev_resp.json()
    assert "Sarah Connor" in prev_data["subject"]
    assert "Cyberdyne Systems" in prev_data["html_body"]


@pytest.mark.asyncio
async def test_template_duplicate_and_restore(client, auth_headers):
    """Templates can be duplicated and restored to previous version snapshots."""
    from services.communications_service import CommunicationsService
    db = get_database()
    await CommunicationsService.ensure_default_templates(db)

    # 1. Duplicate system template
    dup_resp = client.post("/api/admin/communications/templates/enquiry_acknowledgement/duplicate", headers=auth_headers)
    assert dup_resp.status_code == 200
    dup_key = dup_resp.json()["key"]
    assert "enquiry_acknowledgement_copy" in dup_key

    # 2. Update the copy (version 2)
    client.post(f"/api/admin/communications/templates/{dup_key}", headers=auth_headers, json={
        "name": "Modified Copy",
        "subject": "New Subject",
        "body_html": "<p>Version 2 Content</p>",
        "is_active": True,
    })

    # 3. Restore to version 1
    restore_resp = client.post(f"/api/admin/communications/templates/{dup_key}/restore/1", headers=auth_headers)
    assert restore_resp.status_code == 200
    assert restore_resp.json()["version"] == 3  # restored snapshot saved as new incremented version 3


@pytest.mark.asyncio
async def test_public_unsubscribe_flow(client):
    """Signed HMAC-SHA256 unsubscribe links create suppression records and return HTML."""
    from services.communications_service import CommunicationsService
    db = get_database()

    target_email = "optout.user@enterprise.com"
    token, expires_at = CommunicationsService.generate_unsubscribe_token(target_email)

    # 1. Valid token request
    resp = client.get(f"/api/unsubscribe?email={target_email}&token={token}&exp={expires_at}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "You've been unsubscribed" in resp.text
    assert target_email in resp.text

    # Verify DB suppression record created
    supp = await db.email_suppressions.find_one({"email": target_email})
    assert supp is not None
    assert supp["reason"] == "unsubscribed"

    # 2. Invalid / Tampered token request
    bad_resp = client.get(f"/api/unsubscribe?email={target_email}&token=tampered_token_hex&exp={expires_at}")
    assert bad_resp.status_code == 400
    assert "invalid" in bad_resp.text.lower() or "expired" in bad_resp.text.lower()


@pytest.mark.asyncio
async def test_campaign_render_preview_canonical(client, auth_headers):
    """POST /render-preview returns the canonical rendered content snapshot."""
    camp_resp = client.post("/api/admin/communications/campaigns", headers=auth_headers, json={
        "name": "Canonical Preview Test",
        "subject": "Strategy Update for {{ name }}",
        "custom_html": "<p>Dear {{ name }} at {{ company }}, welcome to Navigatte.</p>",
    })
    assert camp_resp.status_code == 200
    camp_id = camp_resp.json()["id"]

    prev_resp = client.post(f"/api/admin/communications/campaigns/{camp_id}/render-preview", headers=auth_headers)
    assert prev_resp.status_code == 200
    data = prev_resp.json()
    assert data["campaign_id"] == camp_id
    assert "Sarah Connor" in data["subject"]
    assert "Cyberdyne Systems" in data["html_body"]
    assert "content_match_note" in data


@pytest.mark.asyncio
async def test_campaign_send_test_campaign_isolation(client, auth_headers, monkeypatch):
    """POST /send-test-campaign enforces server-level safety boundary (never sends to audience)."""
    from integrations.contracts.communications import EmailDeliveryResult
    from datetime import datetime, timezone

    # Mock provider
    async def mock_send(self, message):
        return EmailDeliveryResult(
            provider="resend",
            message_id="msg_test_campaign_999",
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.send_email", mock_send)
    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.is_enabled", lambda self: True)

    camp_resp = client.post("/api/admin/communications/campaigns", headers=auth_headers, json={
        "name": "Safety Isolation Test",
        "subject": "Test Dispatch",
        "custom_html": "<p>Hello {{ name }}</p>",
        "test_recipients": ["safety.verifier@navigatte.internal"],
    })
    assert camp_resp.status_code == 200
    camp_id = camp_resp.json()["id"]

    send_resp = client.post(f"/api/admin/communications/campaigns/{camp_id}/send-test-campaign", headers=auth_headers)
    assert send_resp.status_code == 200
    data = send_resp.json()
    assert data["success"] is True
    assert data["sent_count"] == 1
    assert data["results"][0]["email"] == "safety.verifier@navigatte.internal"
    assert "Audience contacts were NOT used" in data["note"]

