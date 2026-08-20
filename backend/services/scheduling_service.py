"""Scheduling Service (Core CRM Domain).

Processes normalized SchedulingEvent domain objects, enforces durable database idempotency,
matches attendees to CRM enquiries, maintains scheduling status and timeline activity logs.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from integrations.contracts.scheduling import (
    SchedulingEvent,
    SchedulingEventType,
)
from models.enquiry import (
    BookingSummary,
    Enquiry,
    EnquiryActivity,
    EnquiryStatus,
    SchedulingStatus,
)
from models.webhook_event import (
    IntegrationWebhookEvent,
    WebhookProcessingStatus,
)

logger = logging.getLogger(__name__)

EVENT_TO_SCHEDULING_STATUS: Dict[SchedulingEventType, SchedulingStatus] = {
    SchedulingEventType.BOOKING_CREATED: SchedulingStatus.BOOKED,
    SchedulingEventType.BOOKING_RESCHEDULED: SchedulingStatus.RESCHEDULED,
    SchedulingEventType.BOOKING_CANCELLED: SchedulingStatus.CANCELLED,
    SchedulingEventType.BOOKING_REJECTED: SchedulingStatus.CANCELLED,
    SchedulingEventType.BOOKING_COMPLETED: SchedulingStatus.COMPLETED,
    SchedulingEventType.BOOKING_NO_SHOW: SchedulingStatus.NO_SHOW,
}


def _format_datetime_human(dt: Optional[datetime], tz_name: Optional[str] = None) -> str:
    if not dt:
        return "TBD"
    formatted = dt.strftime("%b %d, %Y at %I:%M %p")
    if tz_name:
        formatted += f" ({tz_name})"
    return formatted


def _build_activity(event: SchedulingEvent) -> EnquiryActivity:
    meeting = event.meeting
    start_str = _format_datetime_human(meeting.start_at if meeting else None, meeting.time_zone if meeting else None)

    if event.event_type == SchedulingEventType.BOOKING_CREATED:
        return EnquiryActivity(
            type="booking_created",
            title="Consultation Call Booked",
            summary=f"Call scheduled for {start_str}",
            source=event.provider,
            timestamp=event.occurred_at,
            metadata={
                "booking_uid": event.external_booking_uid,
                "meeting_url": meeting.meeting_url if meeting else None,
                "title": meeting.title if meeting else None,
                "event_type": meeting.event_type_slug if meeting else None,
            },
        )
    elif event.event_type == SchedulingEventType.BOOKING_RESCHEDULED:
        return EnquiryActivity(
            type="booking_rescheduled",
            title="Consultation Call Rescheduled",
            summary=f"Call rescheduled to {start_str}",
            source=event.provider,
            timestamp=event.occurred_at,
            metadata={
                "booking_uid": event.external_booking_uid,
                "meeting_url": meeting.meeting_url if meeting else None,
            },
        )
    elif event.event_type == SchedulingEventType.BOOKING_CANCELLED:
        reason = event.raw_metadata.get("cal_cancellation_reason") or "No cancellation reason provided"
        return EnquiryActivity(
            type="booking_cancelled",
            title="Consultation Call Cancelled",
            summary=f"Call cancelled. Note: {reason}",
            source=event.provider,
            timestamp=event.occurred_at,
            metadata={
                "booking_uid": event.external_booking_uid,
                "cancellation_reason": reason,
            },
        )
    elif event.event_type == SchedulingEventType.MEETING_STARTED:
        return EnquiryActivity(
            type="meeting_started",
            title="Meeting Commenced",
            summary="Virtual meeting session started with attendee",
            source=event.provider,
            timestamp=event.occurred_at,
            metadata={"booking_uid": event.external_booking_uid},
        )
    elif event.event_type == SchedulingEventType.MEETING_ENDED:
        return EnquiryActivity(
            type="meeting_ended",
            title="Meeting Concluded",
            summary="Virtual meeting session concluded",
            source=event.provider,
            timestamp=event.occurred_at,
            metadata={"booking_uid": event.external_booking_uid},
        )
    elif event.event_type == SchedulingEventType.BOOKING_NO_SHOW:
        return EnquiryActivity(
            type="booking_no_show",
            title="Attendee No-Show",
            summary="Attendee marked as no-show for scheduled call",
            source=event.provider,
            timestamp=event.occurred_at,
            metadata={"booking_uid": event.external_booking_uid},
        )
    else:
        return EnquiryActivity(
            type=f"scheduling_{event.event_type.value.lower()}",
            title=f"Scheduling Update: {event.event_type.value}",
            summary=f"Received scheduling update for booking {event.external_booking_uid}",
            source=event.provider,
            timestamp=event.occurred_at,
            metadata=event.raw_metadata,
        )


class SchedulingService:
    @staticmethod
    async def process_event(
        event: SchedulingEvent,
        db: AsyncIOMotorDatabase,
        signature_verified: bool = True,
    ) -> Tuple[Optional[Enquiry], Dict[str, Any]]:
        """Idempotently ingests and processes a normalized SchedulingEvent into the CRM.

        Returns (Enquiry, status_dict).
        """
        now = datetime.now(timezone.utc)

        # 1. Idempotency Check: Query existing webhook event record
        existing_event = await db.integration_webhook_events.find_one(
            {"idempotency_key": event.idempotency_key}
        )

        if existing_event and existing_event.get("processing_status") == WebhookProcessingStatus.PROCESSED.value:
            logger.info(f"Duplicate webhook event ignored: {event.idempotency_key}")
            enquiry_id = existing_event.get("entity_reference")
            matched_enquiry = None
            if enquiry_id and ObjectId.is_valid(enquiry_id):
                doc = await db.enquiries.find_one({"_id": ObjectId(enquiry_id)})
                if doc:
                    matched_enquiry = Enquiry.from_mongo(doc)
            return matched_enquiry, {
                "status": "duplicate",
                "idempotency_key": event.idempotency_key,
                "message": "Event already processed successfully",
            }

        # 2. Insert or update webhook event record as RECEIVED
        webhook_event = IntegrationWebhookEvent(
            provider=event.provider,
            event_type=event.event_type.value,
            idempotency_key=event.idempotency_key,
            external_event_id=event.external_event_id,
            external_booking_uid=event.external_booking_uid,
            received_at=now,
            processing_status=WebhookProcessingStatus.RECEIVED,
            signature_verified=signature_verified,
            sanitized_payload=event.raw_metadata,
        )

        try:
            insert_result = await db.integration_webhook_events.insert_one(webhook_event.to_mongo())
            event_db_id = insert_result.inserted_id
        except DuplicateKeyError:
            # Race condition: another worker already received it
            existing_event = await db.integration_webhook_events.find_one(
                {"idempotency_key": event.idempotency_key}
            )
            event_db_id = existing_event["_id"] if existing_event else None

        # 3. Match Attendee to Existing Enquiry by Email
        normalized_email = event.attendee.email.strip().lower()
        email_query = {"email": {"$regex": f"^{re.escape(normalized_email)}$", "$options": "i"}}

        # Exclude synthetic test leads from customer matching unless target attendee email matches test
        if not normalized_email.startswith("rca_verification_test@"):
            email_query["is_test"] = {"$ne": True}

        cursor = db.enquiries.find(email_query).sort("created_at", -1)
        existing_docs = await cursor.to_list(1)

        activity = _build_activity(event)
        new_scheduling_status = EVENT_TO_SCHEDULING_STATUS.get(
            event.event_type, SchedulingStatus.BOOKED
        )

        meeting = event.meeting
        booking_summary = BookingSummary(
            provider=event.provider,
            booking_uid=event.external_booking_uid,
            event_title=meeting.title if meeting else None,
            event_type_slug=meeting.event_type_slug if meeting else None,
            scheduled_start=meeting.start_at if meeting else None,
            scheduled_end=meeting.end_at if meeting else None,
            timezone=meeting.time_zone if meeting else None,
            meeting_url=meeting.meeting_url if meeting else None,
            status=new_scheduling_status,
            updated_at=now,
        )

        enquiry: Optional[Enquiry] = None

        if existing_docs:
            # Case A: Match existing Enquiry
            doc = existing_docs[0]
            enquiry_id = doc["_id"]

            update_fields: Dict[str, Any] = {
                "scheduling_status": new_scheduling_status.value,
                "booking": booking_summary.model_dump(),
                "updated_at": now,
            }

            # If the lead was 'new', advance pipeline to 'contacted'
            if doc.get("status") == EnquiryStatus.NEW.value:
                update_fields["status"] = EnquiryStatus.CONTACTED.value

            # If existing lead lacks phone and incoming attendee provided phone, enrich it
            if not doc.get("phone") and event.attendee.phone:
                update_fields["phone"] = event.attendee.phone

            await db.enquiries.update_one(
                {"_id": enquiry_id},
                {
                    "$set": update_fields,
                    "$push": {"activities": activity.model_dump()},
                },
            )

            updated_doc = await db.enquiries.find_one({"_id": enquiry_id})
            enquiry = Enquiry.from_mongo(updated_doc)
            logger.info(f"Updated existing enquiry {enquiry_id} for booking {event.external_booking_uid}")
        else:
            # Case B: Create new Enquiry representing scheduled prospect
            enquiry = Enquiry(
                name=event.attendee.name,
                email=normalized_email,
                phone=event.attendee.phone,
                company=None,
                service_interest=meeting.event_type_slug if meeting else "Consultation",
                message=meeting.description or f"Direct scheduling consultation booked via {event.provider}",
                source="cal.com",
                status=EnquiryStatus.CONTACTED,
                is_test=normalized_email.startswith("rca_verification_test@"),
                scheduling_status=new_scheduling_status,
                booking=booking_summary,
                activities=[
                    EnquiryActivity(
                        type="enquiry_submitted",
                        title="Direct Booking Created",
                        summary=f"New prospect booked a call via {event.provider}",
                        source=event.provider,
                        timestamp=event.occurred_at,
                    ),
                    activity,
                ],
                created_at=event.occurred_at,
                updated_at=now,
            )

            insert_enquiry = await db.enquiries.insert_one(enquiry.to_mongo())
            enquiry.id = str(insert_enquiry.inserted_id)
            logger.info(f"Created new enquiry {enquiry.id} from booking {event.external_booking_uid}")

        # 4. Mark Webhook Event as PROCESSED
        if event_db_id:
            await db.integration_webhook_events.update_one(
                {"_id": event_db_id},
                {
                    "$set": {
                        "processing_status": WebhookProcessingStatus.PROCESSED.value,
                        "processed_at": now,
                        "entity_reference": enquiry.id,
                        "updated_at": now,
                    }
                },
            )

        return enquiry, {
            "status": "processed",
            "enquiry_id": enquiry.id,
            "event_type": event.event_type.value,
            "idempotency_key": event.idempotency_key,
        }
