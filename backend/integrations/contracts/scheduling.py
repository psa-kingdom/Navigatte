"""Generic Third-Party Scheduling Provider Contract & Normalized Domain Models.

The core Navigatte CRM depends strictly on these contracts, ensuring that Cal.com or
any other scheduling provider can be swapped or removed without CRM code modification.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field


class SchedulingEventType(str, Enum):
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_RESCHEDULED = "BOOKING_RESCHEDULED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_REJECTED = "BOOKING_REJECTED"
    BOOKING_COMPLETED = "BOOKING_COMPLETED"
    BOOKING_NO_SHOW = "BOOKING_NO_SHOW"
    MEETING_STARTED = "MEETING_STARTED"
    MEETING_ENDED = "MEETING_ENDED"
    OTHER = "OTHER"


class SchedulingAttendee(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    time_zone: Optional[str] = None


class SchedulingOrganizer(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    time_zone: Optional[str] = None


class SchedulingMeeting(BaseModel):
    title: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    time_zone: Optional[str] = None
    meeting_url: Optional[str] = None
    event_type_id: Optional[str] = None
    event_type_slug: Optional[str] = None
    description: Optional[str] = None


class SchedulingEvent(BaseModel):
    """Normalized scheduling event ingested from any third-party provider."""
    provider: str  # e.g. "cal.com", "calendly"
    event_type: SchedulingEventType
    idempotency_key: str  # Unique deduplication key
    external_event_id: Optional[str] = None
    external_booking_uid: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attendee: SchedulingAttendee
    organizer: Optional[SchedulingOrganizer] = None
    meeting: Optional[SchedulingMeeting] = None
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)


class SchedulingProvider(ABC):
    """Abstract Base Class for Third-Party Scheduling Adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier e.g. 'cal.com'."""
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Returns True if the provider is enabled and configured in settings."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        """Verifies the authenticity of incoming raw webhook bytes using the configured secret."""
        pass

    @abstractmethod
    def normalize_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> SchedulingEvent:
        """Translates provider-specific JSON payload into a normalized SchedulingEvent."""
        pass

    @abstractmethod
    async def sync_webhook(self, subscriber_url: str) -> Dict[str, Any]:
        """Inspects and registers/updates webhook subscription on the provider account."""
        pass
