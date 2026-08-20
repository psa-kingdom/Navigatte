"""Resend Communications Provider Implementation.

Adheres strictly to the CommunicationsProvider contract.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from core.config import settings
from integrations.contracts.communications import (
    CommunicationsProvider,
    EmailDeliveryResult,
    EmailMessage,
    CommunicationWebhookEvent,
)
from integrations.resend.client import ResendApiClient
from integrations.resend.mapper import map_resend_webhook_to_event
from integrations.resend.verifier import ResendWebhookVerifier

logger = logging.getLogger(__name__)


class ResendCommunicationsProvider(CommunicationsProvider):
    def __init__(
        self,
        client: Optional[ResendApiClient] = None,
        verifier: Optional[ResendWebhookVerifier] = None,
    ):
        self.client = client or ResendApiClient()
        self.verifier = verifier or ResendWebhookVerifier()

    @property
    def name(self) -> str:
        return "resend"

    def is_enabled(self) -> bool:
        return getattr(settings, "RESEND_ENABLED", False) and bool(self.client.api_key)

    async def send_email(self, message: EmailMessage) -> EmailDeliveryResult:
        """Dispatches an email through Resend API."""
        now = datetime.now(timezone.utc)
        if not self.is_enabled():
            logger.info(f"Resend provider is disabled or not configured. Skipping email to {message.to}")
            return EmailDeliveryResult(
                provider=self.name,
                message_id=None,
                status="disabled",
                sent_at=now,
                error="Resend provider is not enabled or RESEND_API_KEY is not set.",
            )

        try:
            to_emails = [r.email for r in message.to]
            resp = await self.client.send_email(
                to=to_emails,
                subject=message.subject,
                from_email=message.from_email,
                html=message.html_body,
                text=message.text_body,
                reply_to=message.reply_to,
                tags=message.tags,
            )
            msg_id = resp.get("id")
            return EmailDeliveryResult(
                provider=self.name,
                message_id=msg_id,
                status="sent",
                sent_at=now,
                raw_response=resp,
            )
        except Exception as e:
            logger.error(f"Failed to send email via Resend: {e}")
            return EmailDeliveryResult(
                provider=self.name,
                message_id=None,
                status="failed",
                sent_at=now,
                error=str(e),
            )

    def verify_webhook_signature(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        """Verifies inbound webhook signature from Resend / Svix."""
        return self.verifier.verify(raw_body, headers)

    def normalize_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> CommunicationWebhookEvent:
        """Translates Resend webhook payload into normalized CommunicationWebhookEvent."""
        return map_resend_webhook_to_event(payload, headers)
