"""Canonical Render Parity & Contract Reconciliation Tests.

Ensures:
1. Preview HTML == Outbox.body_html == Provider Payload HTML (Exact Content Guarantee).
2. Custom HTML is delivered as-is without silent fallback or template re-querying.
3. Single canonical /send-test endpoint handles single and multi-recipient dispatches.
4. Deployment parity version endpoint returns required metadata.
"""

from datetime import datetime, timezone
import pytest
from core.database import get_database
from models.communications import EmailTemplateModel, OutboxItemModel, OutboxStatus
from services.communications_service import CommunicationsService


@pytest.mark.asyncio
async def test_exact_content_guarantee_preview_equals_outbox_equals_provider(client, auth_headers, monkeypatch):
    """LITERAL EXACT CONTENT GUARANTEE:
    
    Preview HTML == Outbox.body_html == Provider Payload HTML
    No divergence, no template re-fetching, no silent substitution.
    """
    from integrations.contracts.communications import EmailDeliveryResult
    db = get_database()

    dispatched_messages = []

    async def mock_send_email(self, message):
        dispatched_messages.append(message)
        return EmailDeliveryResult(
            provider="resend",
            message_id="msg_parity_test_888",
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.send_email", mock_send_email)
    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.is_enabled", lambda self: True)

    custom_html_authored = (
        "<div style='font-family: Arial;'>"
        "<h1>Q3 Strategic Technology Advisory</h1>"
        "<p>Hello {{ name }}, your enterprise consultation at {{ company }} is set.</p>"
        "<a href='{{ meeting_url }}'>Join Strategy Room</a>"
        "</div>"
    )
    subject_authored = "Strategic Advisory for {{ name }}"
    vars_provided = {
        "name": "Sarah Connor",
        "company": "Cyberdyne Systems",
        "meeting_url": "https://navigatte.com/meet/sarah-connor",
    }

    # 1. Canonical Render Pipeline generates the preview/snapshot
    snapshot = await CommunicationsService.render_message(
        db,
        custom_html=custom_html_authored,
        subject=subject_authored,
        variables=vars_provided,
    )

    # 2. Dispatch via canonical send-test endpoint
    resp = client.post(
        "/api/admin/communications/send-test",
        headers=auth_headers,
        json={
            "recipient_email": "sarah.connor@cyberdyne.io",
            "subject": subject_authored,
            "custom_html": custom_html_authored,
            "variables": vars_provided,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # 3. Check outbox document in DB
    outbox_doc = await db.email_outbox.find_one({"_id": data["outbox_id"]})
    assert outbox_doc is not None

    # 4. Check intercepted provider message
    assert len(dispatched_messages) == 1
    provider_msg = dispatched_messages[0]

    # 5. LITERAL EXACT EQUALITY ASSERTIONS:
    # A. Subject parity
    assert snapshot.subject == outbox_doc["subject"] == provider_msg.subject == "Strategic Advisory for Sarah Connor"

    # B. Body HTML parity
    assert snapshot.body_html == outbox_doc["body_html"] == provider_msg.html_body
    assert "Sarah Connor" in provider_msg.html_body
    assert "Cyberdyne Systems" in provider_msg.html_body
    assert "https://navigatte.com/meet/sarah-connor" in provider_msg.html_body


@pytest.mark.asyncio
async def test_send_test_multi_recipients_support(client, auth_headers, monkeypatch):
    """Canonical send-test accepts recipient_emails array and delivers to all specified test targets."""
    from integrations.contracts.communications import EmailDeliveryResult

    dispatched = []

    async def mock_send(self, message):
        dispatched.append(message)
        return EmailDeliveryResult(
            provider="resend",
            message_id=f"msg_{len(dispatched)}",
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.send_email", mock_send)
    monkeypatch.setattr("integrations.resend.provider.ResendCommunicationsProvider.is_enabled", lambda self: True)

    resp = client.post(
        "/api/admin/communications/send-test",
        headers=auth_headers,
        json={
            "recipient_emails": ["qa1@navigatte.internal", "qa2@navigatte.internal"],
            "subject": "Test Dispatch Batch",
            "custom_html": "<p>Test Content</p>",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["sent_count"] == 2
    assert len(dispatched) == 2
    recipients_sent = {m.to[0].email for m in dispatched}
    assert recipients_sent == {"qa1@navigatte.internal", "qa2@navigatte.internal"}


@pytest.mark.asyncio
async def test_system_version_parity_endpoint(client):
    """GET /api/system/version returns build version and communications parity status."""
    resp = client.get("/api/system/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["application"] == "Navigatte API"
    assert "version" in data
    assert "communications_version" in data
    assert data["canonical_render"] == "enabled"
