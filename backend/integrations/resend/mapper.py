"""Resend Webhook Payload Mapper.

Translates Resend webhook JSON payloads into normalized CommunicationWebhookEvent objects.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from integrations.contracts.communications import (
    CommunicationEventType,
    CommunicationWebhookEvent,
)

logger = logging.getLogger(__name__)

RESEND_EVENT_MAP: Dict[str, CommunicationEventType] = {
    "email.sent": CommunicationEventType.SENT,
    "email.delivered": CommunicationEventType.DELIVERED,
    "email.delivery_delayed": CommunicationEventType.DELIVERY_DELAYED,
    "email.bounced": CommunicationEventType.BOUNCED,
    "email.complained": CommunicationEventType.COMPLAINED,
    "email.opened": CommunicationEventType.OPENED,
    "email.clicked": CommunicationEventType.CLICKED,
}


def map_resend_webhook_to_event(
    payload_dict: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> CommunicationWebhookEvent:
    """Maps a raw Resend webhook payload to normalized CommunicationWebhookEvent."""
    raw_type = str(payload_dict.get("type", "")).lower()
    event_type = RESEND_EVENT_MAP.get(raw_type, CommunicationEventType.OTHER)

    data = payload_dict.get("data") or {}
    message_id = str(data.get("email_id") or data.get("id") or "")
    recipient = None
    if isinstance(data.get("to"), list) and data["to"]:
        recipient = str(data["to"][0])
    elif isinstance(data.get("to"), str):
        recipient = data["to"]

    created_at_raw = payload_dict.get("created_at") or data.get("created_at")
    occurred_at = datetime.now(timezone.utc)
    if created_at_raw:
        try:
            cleaned = str(created_at_raw).replace("Z", "+00:00")
            occurred_at = datetime.fromisoformat(cleaned)
            if not occurred_at.tzinfo:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        except Exception:
            occurred_at = datetime.now(timezone.utc)

    # Deterministic idempotency key
    idempotency_key = f"resend_{message_id}_{raw_type}_{occurred_at.isoformat()}"

    return CommunicationWebhookEvent(
        provider="resend",
        event_type=event_type,
        idempotency_key=idempotency_key,
        external_message_id=message_id,
        recipient_email=recipient,
        occurred_at=occurred_at,
        raw_payload=payload_dict,
    )
