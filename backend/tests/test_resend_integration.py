"""Tests for Resend Communications Provider and Webhook Verification."""

import base64
import hashlib
import hmac
import time
import pytest
from core.config import settings
from integrations.contracts.communications import (
    CommunicationEventType,
    EmailMessage,
    EmailRecipient,
)
from integrations.resend.client import ResendApiClient
from integrations.resend.mapper import map_resend_webhook_to_event
from integrations.resend.provider import ResendCommunicationsProvider
from integrations.resend.verifier import ResendWebhookVerifier


def test_resend_provider_disabled_without_credentials(monkeypatch):
    """Verifies that Resend provider fails gracefully and does not crash when unconfigured."""
    monkeypatch.setattr(settings, "RESEND_ENABLED", False)
    monkeypatch.setattr(settings, "RESEND_API_KEY", None)

    provider = ResendCommunicationsProvider()
    assert not provider.is_enabled()
    assert provider.name == "resend"

    msg = EmailMessage(
        to=[EmailRecipient(email="client@example.com", name="Client")],
        subject="Welcome to Navigatte",
        text_body="Hello from Navigatte",
    )

    import asyncio
    result = asyncio.run(provider.send_email(msg))
    assert result.status == "provider_disabled"
    assert result.message_id is None
    assert "resend_api_key" in result.error.lower() or "not enabled" in result.error.lower()


def test_resend_webhook_signature_verification():
    """Verifies Svix / Resend HMAC-SHA256 signature algorithm."""
    secret_bytes = b"0123456789abcdef0123456789abcdef"
    secret_b64 = base64.b64encode(secret_bytes).decode("utf-8")
    secret = f"whsec_{secret_b64}"
    verifier = ResendWebhookVerifier(secret=secret)

    raw_body = b'{"type":"email.delivered","data":{"id":"msg_123","to":["client@example.com"]}}'
    msg_id = "msg_svix_test_001"
    msg_timestamp = str(int(time.time()))

    # Compute expected signature
    to_sign = f"{msg_id}.{msg_timestamp}.".encode("utf-8") + raw_body
    sig_bytes = hmac.new(secret_bytes, to_sign, hashlib.sha256).digest()
    sig_b64 = base64.b64encode(sig_bytes).decode("utf-8")

    valid_headers = {
        "svix-id": msg_id,
        "svix-timestamp": msg_timestamp,
        "svix-signature": f"v1,{sig_b64}",
    }
    assert verifier.verify(raw_body, valid_headers) is True

    # Invalid signature header
    invalid_headers = {
        "svix-id": msg_id,
        "svix-timestamp": msg_timestamp,
        "svix-signature": "v1,invalid_signature_hash",
    }
    assert verifier.verify(raw_body, invalid_headers) is False

    # Missing headers
    assert verifier.verify(raw_body, {}) is False


def test_resend_event_mapper():
    """Verifies mapping from Resend webhook payload to normalized CommunicationWebhookEvent."""
    delivered_payload = {
        "type": "email.delivered",
        "created_at": "2026-08-20T10:00:00.000Z",
        "data": {
            "id": "email_del_999",
            "to": ["prospect@acme.corp"],
            "subject": "Proposal Discussion",
        },
    }
    event = map_resend_webhook_to_event(delivered_payload)
    assert event.provider == "resend"
    assert event.event_type == CommunicationEventType.DELIVERED
    assert event.external_message_id == "email_del_999"
    assert event.recipient_email == "prospect@acme.corp"
    assert "resend_email_del_999" in event.idempotency_key

    bounced_payload = {
        "type": "email.bounced",
        "created_at": "2026-08-20T10:05:00.000Z",
        "data": {
            "id": "email_bnc_888",
            "to": ["invalid@nowhere.corp"],
        },
    }
    bounce_event = map_resend_webhook_to_event(bounced_payload)
    assert bounce_event.event_type == CommunicationEventType.BOUNCED
    assert bounce_event.recipient_email == "invalid@nowhere.corp"


def test_admin_integrations_status_includes_resend(client, auth_headers):
    """Verifies that GET /api/admin/integrations/status includes Cal and Resend metadata."""
    resp = client.get("/api/admin/integrations/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "cal" in data
    assert data["cal"]["name"] == "Cal.com"

    assert "resend" in data
    assert data["resend"]["name"] == "Resend"
    assert data["resend"]["sending_domain"] == "updates.navigatte.com"
    assert "has_api_key" in data["resend"]
