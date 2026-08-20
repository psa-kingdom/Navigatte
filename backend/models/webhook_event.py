"""Integration Webhook Event document model for durable idempotency and auditing."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import Field
from models.base import BaseDocument


class WebhookProcessingStatus(str, Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class IntegrationWebhookEvent(BaseDocument):
    provider: str  # e.g. "cal.com"
    event_type: str  # e.g. "BOOKING_CREATED", "BOOKING_RESCHEDULED", "BOOKING_CANCELLED"
    idempotency_key: str  # Unique deduplication key e.g. "cal:BOOKING_CREATED:uid123:timestamp"
    external_event_id: Optional[str] = None
    external_booking_uid: Optional[str] = None
    payload_version: Optional[str] = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    processing_status: WebhookProcessingStatus = WebhookProcessingStatus.RECEIVED
    attempt_count: int = 1
    error_message: Optional[str] = None
    signature_verified: bool = False
    sanitized_payload: Optional[Dict[str, Any]] = None
    entity_reference: Optional[str] = None  # Matched Enquiry ID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
