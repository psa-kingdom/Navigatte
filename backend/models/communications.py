"""Database and Domain Models for Communications & Email Outbox."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field
import uuid


class OutboxStatus(str, Enum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    FAILED = "failed"
    OPENED = "opened"
    CLICKED = "clicked"


class EmailTemplateModel(BaseModel):
    """Database model for transactional and notification email templates."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    key: str  # e.g. 'enquiry_acknowledgement', 'consultation_booking_confirmation'
    name: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> Dict[str, Any]:
        return {
            "_id": self.id,
            "key": self.key,
            "name": self.name,
            "subject": self.subject,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "variables": self.variables,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "EmailTemplateModel":
        if not data:
            return None
        doc = dict(data)
        doc["id"] = str(doc.pop("_id", data.get("id")))
        return cls(**doc)


class OutboxItemModel(BaseModel):
    """Durable Outbox record representing an outbound email message."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    idempotency_key: str
    template_key: Optional[str] = None
    recipient_email: EmailStr
    recipient_name: Optional[str] = None
    subject: str
    body_html: str
    body_text: Optional[str] = None
    from_email: str = "Navigatte <updates@updates.navigatte.com>"
    status: OutboxStatus = OutboxStatus.QUEUED
    provider: str = "resend"
    provider_message_id: Optional[str] = None
    enquiry_id: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> Dict[str, Any]:
        return {
            "_id": self.id,
            "idempotency_key": self.idempotency_key,
            "template_key": self.template_key,
            "recipient_email": self.recipient_email,
            "recipient_name": self.recipient_name,
            "subject": self.subject,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "from_email": self.from_email,
            "status": self.status.value if isinstance(self.status, OutboxStatus) else str(self.status),
            "provider": self.provider,
            "provider_message_id": self.provider_message_id,
            "enquiry_id": self.enquiry_id,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
            "delivered_at": self.delivered_at,
            "opened_at": self.opened_at,
            "clicked_at": self.clicked_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "OutboxItemModel":
        if not data:
            return None
        doc = dict(data)
        doc["id"] = str(doc.pop("_id", data.get("id")))
        return cls(**doc)
