"""Cal.com Webhook Pydantic Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class CalAttendee(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    timeZone: Optional[str] = None
    phoneNumber: Optional[str] = None


class CalOrganizer(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    timeZone: Optional[str] = None


class CalVideoCallData(BaseModel):
    url: Optional[str] = None
    type: Optional[str] = None


class CalBookingPayload(BaseModel):
    uid: Optional[str] = None
    id: Optional[Union[str, int]] = None
    title: Optional[str] = None
    startTime: Optional[Union[str, datetime]] = None
    endTime: Optional[Union[str, datetime]] = None
    attendees: List[CalAttendee] = Field(default_factory=list)
    organizer: Optional[CalOrganizer] = None
    type: Optional[str] = None  # Event type slug / name
    eventTypeId: Optional[Union[str, int]] = None
    description: Optional[str] = None
    meetingUrl: Optional[str] = None
    videoCallData: Optional[CalVideoCallData] = None
    status: Optional[str] = None
    rescheduleUid: Optional[str] = None
    rescheduledBy: Optional[str] = None
    cancellationReason: Optional[str] = None
    customInputs: Optional[Dict[str, Any]] = None


class CalWebhookEnvelope(BaseModel):
    """Top-level webhook envelope sent by Cal.com."""
    triggerEvent: str
    createdAt: Optional[Union[str, datetime]] = None
    payload: Optional[Union[CalBookingPayload, Dict[str, Any]]] = None
