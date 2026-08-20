"""Generic Third-Party Communications Provider Contract & Domain Models.

Ensures that email delivery (transactional, campaign, notification) remains strictly
abstracted behind a provider-neutral boundary. Resend, SendGrid, Postmark, or AWS SES
can be swapped or removed without altering CRM, Enquiry, or Campaign business logic.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field


class CommunicationEventType(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    DELIVERY_DELAYED = "DELIVERY_DELAYED"
    BOUNCED = "BOUNCED"
    COMPLAINED = "COMPLAINED"
    OPENED = "OPENED"
    CLICKED = "CLICKED"
    FAILED = "FAILED"
    OTHER = "OTHER"


class EmailRecipient(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class EmailAttachment(BaseModel):
    filename: str
    content: str  # Base64 or plain string
    content_type: str = "application/octet-stream"


class EmailMessage(BaseModel):
    """Normalized email message structure for outbound dispatch."""
    to: List[EmailRecipient]
    subject: str
    html_body: Optional[str] = None
    text_body: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    cc: List[EmailRecipient] = Field(default_factory=list)
    bcc: List[EmailRecipient] = Field(default_factory=list)
    attachments: List[EmailAttachment] = Field(default_factory=list)
    tags: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class EmailDeliveryResult(BaseModel):
    """Normalized delivery dispatch confirmation."""
    provider: str  # e.g. "resend"
    message_id: Optional[str] = None
    status: str  # "sent", "queued", "failed", "disabled"
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    raw_response: Dict[str, Any] = Field(default_factory=dict)


class CommunicationWebhookEvent(BaseModel):
    """Normalized inbound delivery tracking event (delivery, bounce, open, click)."""
    provider: str
    event_type: CommunicationEventType
    idempotency_key: str
    external_message_id: str
    recipient_email: Optional[str] = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class CommunicationsProvider(ABC):
    """Abstract Base Class for Third-Party Communications / Email Adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier e.g. 'resend'."""
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Returns True if provider credentials are fully configured."""
        pass

    @abstractmethod
    async def send_email(self, message: EmailMessage) -> EmailDeliveryResult:
        """Dispatches an email message through the provider."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        """Verifies inbound webhook authenticity (e.g. Svix signature)."""
        pass

    @abstractmethod
    def normalize_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> CommunicationWebhookEvent:
        """Maps vendor-specific webhook payload into normalized CommunicationWebhookEvent."""
        pass
