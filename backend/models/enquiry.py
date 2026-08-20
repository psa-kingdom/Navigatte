"""Enquiry (CRM Lead) document models and enums."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field
from models.base import BaseDocument


class EnquiryStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    CLOSED = "closed"


class SchedulingStatus(str, Enum):
    NONE = "none"
    BOOKED = "booked"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class EnquiryNote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EnquiryActivity(BaseModel):
    """Activity / timeline event for an enquiry (booking changes, intake submissions, etc.)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # e.g. "enquiry_submitted", "booking_created", "booking_rescheduled", "booking_cancelled", "note_added"
    title: str
    summary: str
    source: str = "system"  # "website_contact", "cal.com", "admin", "system"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BookingSummary(BaseModel):
    """Embedded summary of the latest scheduling booking attached to the enquiry."""
    provider: str = "cal.com"
    booking_uid: str
    event_title: Optional[str] = None
    event_type_slug: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    timezone: Optional[str] = None
    meeting_url: Optional[str] = None
    status: SchedulingStatus = SchedulingStatus.BOOKED
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Enquiry(BaseDocument):
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    service_interest: Optional[str] = None
    message: str
    source: str = "website_contact"
    status: EnquiryStatus = EnquiryStatus.NEW
    is_test: bool = False  # Diagnostic / test data exclusion flag
    scheduling_status: SchedulingStatus = SchedulingStatus.NONE
    booking: Optional[BookingSummary] = None
    notes: List[EnquiryNote] = Field(default_factory=list)
    activities: List[EnquiryActivity] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
