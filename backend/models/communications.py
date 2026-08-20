"""Database and Domain Models for Communications & Email Outbox."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field
import uuid


class OutboxStatus(str, Enum):
    QUEUED = "queued"            # Waiting in a real queue (future worker architecture)
    SENDING = "sending"          # Dispatch in progress
    SENT = "sent"                # Provider accepted the message
    DELIVERED = "delivered"      # Provider confirmed delivery
    BOUNCED = "bounced"          # Hard or soft bounce from provider
    COMPLAINED = "complained"    # Spam complaint registered
    FAILED = "failed"            # Dispatch failed (transient or permanent error)
    OPENED = "opened"            # Recipient opened the email
    CLICKED = "clicked"          # Recipient clicked a link
    PROVIDER_DISABLED = "provider_disabled"  # Provider not configured — no dispatch attempted


class EmailTemplateModel(BaseModel):
    """Database model for transactional and campaign email templates with versioning."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    key: str  # Unique slug key e.g. 'enquiry_acknowledgement'
    name: str
    category: str = "transactional"  # 'transactional' | 'campaign' | 'system'
    subject: str
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = Field(default_factory=list)
    version: int = 1
    is_active: bool = True
    is_system: bool = False  # System-seeded templates cannot be deleted
    provider: str = "navigatte"  # 'navigatte' | 'resend'
    provider_template_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    def to_mongo(self) -> Dict[str, Any]:
        return {
            "_id": self.id,
            "key": self.key,
            "name": self.name,
            "category": self.category,
            "subject": self.subject,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "variables": self.variables,
            "version": self.version,
            "is_active": self.is_active,
            "is_system": self.is_system,
            "provider": self.provider,
            "provider_template_id": self.provider_template_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
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
    attempt_count: int = 0
    max_attempts: int = 3
    next_attempt_at: Optional[datetime] = None
    last_error: Optional[str] = None
    is_retryable: bool = True
    environment: str = "test"    # 'test' | 'production'
    tags: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None
    complained_at: Optional[datetime] = None
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
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "next_attempt_at": self.next_attempt_at,
            "last_error": self.last_error,
            "is_retryable": self.is_retryable,
            "environment": self.environment,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
            "delivered_at": self.delivered_at,
            "opened_at": self.opened_at,
            "clicked_at": self.clicked_at,
            "failed_at": self.failed_at,
            "bounced_at": self.bounced_at,
            "complained_at": self.complained_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "OutboxItemModel":
        if not data:
            return None
        doc = dict(data)
        doc["id"] = str(doc.pop("_id", data.get("id")))
        return cls(**doc)
