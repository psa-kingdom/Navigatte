"""Cal.com Webhook Payload Mapper.

Transforms Cal.com specific JSON payloads into normalized SchedulingEvent domain objects.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from integrations.contracts.scheduling import (
    SchedulingAttendee,
    SchedulingEvent,
    SchedulingEventType,
    SchedulingMeeting,
    SchedulingOrganizer,
)

logger = logging.getLogger(__name__)

EVENT_TYPE_MAP: Dict[str, SchedulingEventType] = {
    "BOOKING_CREATED": SchedulingEventType.BOOKING_CREATED,
    "BOOKING_RESCHEDULED": SchedulingEventType.BOOKING_RESCHEDULED,
    "BOOKING_CANCELLED": SchedulingEventType.BOOKING_CANCELLED,
    "BOOKING_REJECTED": SchedulingEventType.BOOKING_REJECTED,
    "BOOKING_COMPLETED": SchedulingEventType.BOOKING_COMPLETED,
    "BOOKING_NO_SHOW": SchedulingEventType.BOOKING_NO_SHOW,
    "BOOKING_NO_SHOW_UPDATED": SchedulingEventType.BOOKING_NO_SHOW,
    "MEETING_STARTED": SchedulingEventType.MEETING_STARTED,
    "MEETING_ENDED": SchedulingEventType.MEETING_ENDED,
}


def _parse_dt(val: Any) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            cleaned = val.replace("Z", "+00:00") if val.endswith("Z") else val
            parsed = datetime.fromisoformat(cleaned)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def map_cal_webhook_to_event(
    payload_dict: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> SchedulingEvent:
    """Maps a raw Cal.com webhook dict to a normalized SchedulingEvent.

    Handles both nested { triggerEvent, payload: {...} } format and flat format.
    """
    raw_trigger = payload_dict.get("triggerEvent", "BOOKING_CREATED").upper()
    event_type = EVENT_TYPE_MAP.get(raw_trigger, SchedulingEventType.OTHER)

    # Extract nested booking payload if present; fallback to top-level dict
    inner = payload_dict.get("payload")
    if not isinstance(inner, dict):
        inner = payload_dict

    booking_uid = str(inner.get("uid") or inner.get("bookingId") or inner.get("id") or "unknown_booking")
    created_at_raw = payload_dict.get("createdAt") or inner.get("createdAt")
    occurred_at = _parse_dt(created_at_raw) or datetime.now(timezone.utc)

    # Extract Attendees
    attendees_raw = inner.get("attendees") or []
    primary_attendee: Dict[str, Any] = {}
    if isinstance(attendees_raw, list) and len(attendees_raw) > 0:
        primary_attendee = attendees_raw[0] if isinstance(attendees_raw[0], dict) else {}
    elif isinstance(inner.get("attendee"), dict):
        primary_attendee = inner.get("attendee")

    attendee_name = str(primary_attendee.get("name") or inner.get("name") or "").strip()
    raw_email = primary_attendee.get("email") or inner.get("email") or ""

    # Check responses object if name/email not directly in attendees
    responses = inner.get("responses") or {}
    if isinstance(responses, dict):
        if not raw_email:
            email_resp = responses.get("email")
            if isinstance(email_resp, dict):
                raw_email = email_resp.get("value") or ""
            elif isinstance(email_resp, str):
                raw_email = email_resp
        if not attendee_name:
            name_resp = responses.get("name")
            if isinstance(name_resp, dict):
                attendee_name = name_resp.get("value") or ""
            elif isinstance(name_resp, str):
                attendee_name = name_resp

    attendee_name = attendee_name or "Prospective Client"
    raw_email = raw_email or "unknown@prospect.navigatte.com"
    attendee_email = str(raw_email).strip().lower()
    attendee_phone = primary_attendee.get("phoneNumber") or inner.get("phoneNumber") or primary_attendee.get("phone")
    attendee_tz = primary_attendee.get("timeZone") or inner.get("timeZone")

    attendee = SchedulingAttendee(
        name=attendee_name,
        email=attendee_email,
        phone=str(attendee_phone).strip() if attendee_phone else None,
        time_zone=str(attendee_tz).strip() if attendee_tz else None,
    )

    # Extract Organizer
    organizer_raw = inner.get("organizer") or {}
    organizer: Optional[SchedulingOrganizer] = None
    if isinstance(organizer_raw, dict) and organizer_raw:
        organizer = SchedulingOrganizer(
            name=organizer_raw.get("name"),
            email=organizer_raw.get("email"),
            time_zone=organizer_raw.get("timeZone"),
        )

    # Extract Meeting Details
    meeting_url = (
        inner.get("meetingUrl")
        or inner.get("videoCallUrl")
        or (inner.get("videoCallData", {}).get("url") if isinstance(inner.get("videoCallData"), dict) else None)
        or (inner.get("location") if isinstance(inner.get("location"), str) and inner.get("location").startswith("http") else None)
    )

    meeting = SchedulingMeeting(
        title=inner.get("title") or "Consultation Call",
        start_at=_parse_dt(inner.get("startTime")),
        end_at=_parse_dt(inner.get("endTime")),
        time_zone=inner.get("timeZone") or attendee_tz,
        meeting_url=meeting_url,
        event_type_id=str(inner.get("eventTypeId")) if inner.get("eventTypeId") is not None else None,
        event_type_slug=inner.get("type"),
        description=inner.get("description"),
    )

    # Compute deterministic idempotency key
    # e.g. cal:BOOKING_CREATED:bkg_123:2026-08-25T14:00:00+00:00
    timestamp_marker = (
        meeting.start_at.isoformat()
        if meeting.start_at
        else occurred_at.isoformat()
    )
    idempotency_key = f"cal:{raw_trigger}:{booking_uid}:{timestamp_marker}"

    # Sanitized metadata
    metadata = {
        "cal_trigger_event": raw_trigger,
        "cal_booking_id": inner.get("id"),
        "cal_reschedule_uid": inner.get("rescheduleUid"),
        "cal_cancellation_reason": inner.get("cancellationReason"),
        "cal_status": inner.get("status"),
    }

    return SchedulingEvent(
        provider="cal.com",
        event_type=event_type,
        idempotency_key=idempotency_key,
        external_event_id=str(payload_dict.get("id") or ""),
        external_booking_uid=booking_uid,
        occurred_at=occurred_at,
        attendee=attendee,
        organizer=organizer,
        meeting=meeting,
        raw_metadata=metadata,
    )
