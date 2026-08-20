"""Communications and Transactional Email Engine Service.

Handles template management, idempotent outbox storage, Resend dispatch,
and delivery webhook tracking with CRM timeline correlation.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Literal, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import settings
from integrations.contracts.communications import (
    CommunicationEventType,
    EmailMessage,
    EmailRecipient,
)
from integrations.resend.provider import ResendCommunicationsProvider
from models.communications import EmailTemplateModel, OutboxItemModel, OutboxStatus
from models.enquiry import EnquiryActivity

logger = logging.getLogger(__name__)

# Permanent error substrings — these should NOT be retried
_PERMANENT_ERROR_PATTERNS = [
    "invalid recipient",
    "invalid email",
    "invalid api key",
    "api key",
    "unauthorized",
    "403",
    "suppressed",
    "unsubscribed",
    "invalid sender",
    "domain not verified",
    "malformed",
]

# Default system transactional templates
DEFAULT_TEMPLATES = [
    {
        "key": "enquiry_acknowledgement",
        "name": "Enquiry Intake Acknowledgement",
        "subject": "We've received your enquiry — Navigatte Technical Strategy",
        "body_html": (
            "<div style='font-family: sans-serif; max-width: 600px; margin: 0 auto; color: #111;'>"
            "<h2>Thank you for contacting Navigatte, {{ name }}.</h2>"
            "<p>We have successfully received your enquiry regarding <strong>{{ service_interest }}</strong>.</p>"
            "<p>Our enterprise technology team is reviewing your project requirements and will respond within 24 hours.</p>"
            "<p style='color: #666; font-size: 12px; margin-top: 30px;'>Navigatte Consultancy & Platforms</p>"
            "</div>"
        ),
        "body_text": "Thank you for contacting Navigatte, {{ name }}. We have received your enquiry regarding {{ service_interest }}.",
        "variables": ["name", "service_interest", "company"],
    },
    {
        "key": "consultation_booking_confirmation",
        "name": "Consultation Booking Confirmation",
        "subject": "Confirmed: Navigatte Technical Consultation — {{ start_time }}",
        "body_html": (
            "<div style='font-family: sans-serif; max-width: 600px; margin: 0 auto; color: #111;'>"
            "<h2>Your Consultation is Confirmed</h2>"
            "<p>Hello {{ name }},</p>"
            "<p>Your strategy consultation with Navigatte has been scheduled for <strong>{{ start_time }}</strong> ({{ timezone }}).</p>"
            "<p><a href='{{ meeting_url }}' style='background: #4f46e5; color: #fff; padding: 10px 18px; text-decoration: none; border-radius: 6px;'>Join Video Consultation</a></p>"
            "<p style='color: #666; font-size: 12px; margin-top: 30px;'>Navigatte Consultancy</p>"
            "</div>"
        ),
        "body_text": "Hello {{ name }}, your consultation is confirmed for {{ start_time }}. Join: {{ meeting_url }}",
        "variables": ["name", "start_time", "timezone", "meeting_url"],
    },
    {
        "key": "consultation_rescheduled",
        "name": "Consultation Rescheduled Notice",
        "subject": "Updated Time: Navigatte Technical Consultation — {{ start_time }}",
        "body_html": (
            "<div style='font-family: sans-serif; max-width: 600px; margin: 0 auto; color: #111;'>"
            "<h2>Your Consultation has been Rescheduled</h2>"
            "<p>Hello {{ name }},</p>"
            "<p>Your consultation has been rescheduled to <strong>{{ start_time }}</strong> ({{ timezone }}).</p>"
            "<p><a href='{{ meeting_url }}' style='background: #4f46e5; color: #fff; padding: 10px 18px; text-decoration: none; border-radius: 6px;'>Join Video Consultation</a></p>"
            "</div>"
        ),
        "body_text": "Hello {{ name }}, your consultation has been rescheduled to {{ start_time }}.",
        "variables": ["name", "start_time", "timezone", "meeting_url"],
    },
    {
        "key": "consultation_cancelled",
        "name": "Consultation Cancellation Notice",
        "subject": "Notice: Navigatte Consultation Cancelled",
        "body_html": (
            "<div style='font-family: sans-serif; max-width: 600px; margin: 0 auto; color: #111;'>"
            "<h2>Consultation Cancelled</h2>"
            "<p>Hello {{ name }},</p>"
            "<p>Your scheduled consultation with Navigatte has been cancelled.</p>"
            "<p>If you wish to reschedule at another time, please visit our booking portal.</p>"
            "</div>"
        ),
        "body_text": "Hello {{ name }}, your consultation with Navigatte has been cancelled.",
        "variables": ["name"],
    },
]


class CommunicationsService:
    def __init__(self, provider: Optional[ResendCommunicationsProvider] = None):
        self.provider = provider or ResendCommunicationsProvider()

    @staticmethod
    async def ensure_default_templates(db: AsyncIOMotorDatabase):
        """Seeds default email templates if they do not exist."""
        for tpl_data in DEFAULT_TEMPLATES:
            existing = await db.email_templates.find_one({"key": tpl_data["key"]})
            if not existing:
                tpl = EmailTemplateModel(**tpl_data, is_system=True, category="system")
                await db.email_templates.insert_one(tpl.to_mongo())
                logger.info(f"Seeded default email template: {tpl.key}")

    @staticmethod
    def render_template(body: str, variables: Dict[str, Any]) -> str:
        """Safely interpolates {{ variable }} placeholders."""
        rendered = body
        for key, val in variables.items():
            placeholder = r"\{\{\s*" + re.escape(key) + r"\s*\}\}"
            rendered = re.sub(placeholder, str(val), rendered)
        return rendered

    @staticmethod
    def classify_error(error: Optional[str]) -> Literal["transient", "permanent"]:
        """Classifies a delivery error as transient (retryable) or permanent (do not retry)."""
        if not error:
            return "transient"
        error_lower = error.lower()
        for pattern in _PERMANENT_ERROR_PATTERNS:
            if pattern in error_lower:
                return "permanent"
        return "transient"

    async def send_transactional_email(
        self,
        db: AsyncIOMotorDatabase,
        template_key: str,
        recipient_email: str,
        recipient_name: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        enquiry_id: Optional[str] = None,
        custom_subject: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> OutboxItemModel:
        """Queues, logs, and dispatches a transactional email through the configured provider."""
        vars_dict = variables or {}
        now = datetime.now(timezone.utc)
        idem_key = idempotency_key or f"email:{template_key}:{recipient_email}:{int(now.timestamp())}"

        # 1. Check idempotency in outbox
        existing = await db.email_outbox.find_one({"idempotency_key": idem_key})
        if existing:
            logger.info(f"Email with idempotency key '{idem_key}' already processed.")
            return OutboxItemModel.from_mongo(existing)

        # 2. Fetch template
        tpl_doc = await db.email_templates.find_one({"key": template_key, "is_active": True})
        if tpl_doc:
            subject_raw = custom_subject or tpl_doc.get("subject", "Notification from Navigatte")
            subject = self.render_template(subject_raw, vars_dict)
            body_html = self.render_template(tpl_doc.get("body_html", ""), vars_dict)
            body_text = self.render_template(tpl_doc.get("body_text", ""), vars_dict) if tpl_doc.get("body_text") else None
        else:
            subject = custom_subject or f"Navigatte Notification ({template_key})"
            body_html = f"<p>Notification for {recipient_name or recipient_email}</p>"
            body_text = f"Notification for {recipient_name or recipient_email}"

        from_email = getattr(settings, "RESEND_FROM_EMAIL", "Navigatte <updates@updates.navigatte.com>")
        environment = getattr(settings, "COMMUNICATIONS_ENVIRONMENT", "test")

        # 3. Create Outbox Item (initial status SENDING — will be updated after dispatch)
        outbox_item = OutboxItemModel(
            idempotency_key=idem_key,
            template_key=template_key,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            from_email=from_email,
            status=OutboxStatus.SENDING,
            provider=self.provider.name,
            enquiry_id=enquiry_id,
            attempt_count=1,
            environment=environment,
            metadata=vars_dict,
        )
        await db.email_outbox.insert_one(outbox_item.to_mongo())

        # 4. Dispatch via Provider
        msg = EmailMessage(
            to=[EmailRecipient(email=recipient_email, name=recipient_name)],
            subject=subject,
            html_body=body_html,
            text_body=body_text,
            from_email=from_email,
            idempotency_key=idem_key,
            tags={"template_key": template_key, "enquiry_id": str(enquiry_id or "")},
        )

        result = await self.provider.send_email(msg)

        # 5. Update Outbox Record with Result
        if result.status == "sent":
            outbox_item.status = OutboxStatus.SENT
            outbox_item.provider_message_id = result.message_id
            outbox_item.sent_at = result.sent_at
            outbox_item.last_error = None
            outbox_item.error_message = None
        elif result.status == "provider_disabled":
            outbox_item.status = OutboxStatus.PROVIDER_DISABLED
            outbox_item.error_message = (
                "Email delivery skipped: RESEND_API_KEY is not configured. "
                "Set RESEND_API_KEY in environment variables to enable delivery."
            )
            outbox_item.last_error = result.error
            outbox_item.is_retryable = False
            outbox_item.failed_at = datetime.now(timezone.utc)
        else:
            error_class = self.classify_error(result.error)
            outbox_item.status = OutboxStatus.FAILED
            outbox_item.error_message = result.error
            outbox_item.last_error = result.error
            outbox_item.is_retryable = (error_class == "transient")
            outbox_item.failed_at = datetime.now(timezone.utc)

        outbox_item.updated_at = datetime.now(timezone.utc)
        await db.email_outbox.update_one(
            {"_id": outbox_item.id},
            {"$set": {
                "status": outbox_item.status.value,
                "provider_message_id": outbox_item.provider_message_id,
                "sent_at": outbox_item.sent_at,
                "error_message": outbox_item.error_message,
                "attempt_count": outbox_item.attempt_count,
                "last_error": outbox_item.last_error,
                "is_retryable": outbox_item.is_retryable,
                "failed_at": outbox_item.failed_at,
                "updated_at": outbox_item.updated_at,
            }}
        )

        # 6. If linked to an enquiry, append concise timeline activity
        if enquiry_id and result.status == "sent":
            activity = EnquiryActivity(
                type="email_sent",
                title="Email Dispatched",
                summary=f"Transactional email sent: '{subject}' to {recipient_email}",
                source="system",
                metadata={"template_key": template_key, "provider_message_id": result.message_id},
            )
            await db.enquiries.update_one(
                {"_id": enquiry_id},
                {"$push": {"activities": activity.model_dump()}}
            )

        return outbox_item

    async def retry_outbox_item(
        self,
        db: AsyncIOMotorDatabase,
        outbox_id: str,
    ) -> OutboxItemModel:
        """Manually retries a queued, failed, or provider_disabled outbox item with strict guards."""
        doc = await db.email_outbox.find_one({"_id": outbox_id})
        if not doc:
            raise ValueError(f"Outbox item {outbox_id} not found.")

        outbox_item = OutboxItemModel.from_mongo(doc)
        now = datetime.now(timezone.utc)

        # Guard: Cannot retry already delivered message
        if outbox_item.status == OutboxStatus.DELIVERED:
            raise ValueError(f"Outbox item {outbox_id} is already delivered and cannot be re-sent.")

        # Guard: Check attempt limit
        if outbox_item.attempt_count >= outbox_item.max_attempts:
            raise ValueError(
                f"Outbox item {outbox_id} has reached maximum retry attempts ({outbox_item.max_attempts})."
            )

        msg = EmailMessage(
            to=[EmailRecipient(email=outbox_item.recipient_email, name=outbox_item.recipient_name)],
            subject=outbox_item.subject,
            html_body=outbox_item.body_html,
            text_body=outbox_item.body_text,
            from_email=outbox_item.from_email,
            idempotency_key=f"{outbox_item.idempotency_key}:retry:{outbox_item.attempt_count + 1}",
            tags={"template_key": outbox_item.template_key or "custom", "enquiry_id": str(outbox_item.enquiry_id or "")},
        )

        result = await self.provider.send_email(msg)
        outbox_item.attempt_count += 1
        outbox_item.updated_at = now

        if result.status == "sent":
            outbox_item.status = OutboxStatus.SENT
            outbox_item.provider_message_id = result.message_id
            outbox_item.sent_at = result.sent_at
            outbox_item.error_message = None
            outbox_item.last_error = None
        elif result.status == "provider_disabled":
            outbox_item.status = OutboxStatus.PROVIDER_DISABLED
            outbox_item.error_message = (
                "Email retry skipped: RESEND_API_KEY is not configured. "
                "Set RESEND_API_KEY in environment variables to enable delivery."
            )
            outbox_item.last_error = result.error
            outbox_item.is_retryable = False
            outbox_item.failed_at = now
        else:
            error_class = self.classify_error(result.error)
            outbox_item.status = OutboxStatus.FAILED
            outbox_item.error_message = result.error
            outbox_item.last_error = result.error
            outbox_item.is_retryable = (error_class == "transient")
            outbox_item.failed_at = now

        await db.email_outbox.update_one(
            {"_id": outbox_item.id},
            {"$set": {
                "status": outbox_item.status.value,
                "provider_message_id": outbox_item.provider_message_id,
                "sent_at": outbox_item.sent_at,
                "error_message": outbox_item.error_message,
                "attempt_count": outbox_item.attempt_count,
                "last_error": outbox_item.last_error,
                "is_retryable": outbox_item.is_retryable,
                "failed_at": outbox_item.failed_at,
                "updated_at": outbox_item.updated_at,
            }}
        )

        return outbox_item

    async def process_resend_webhook(
        self,
        db: AsyncIOMotorDatabase,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Processes inbound delivery tracking webhook from Resend (Svix)."""
        event = self.provider.normalize_webhook(payload, headers)
        now = datetime.now(timezone.utc)

        # 1. Idempotency Check in integration_webhook_events
        existing_event = await db.integration_webhook_events.find_one({"idempotency_key": event.idempotency_key})
        if existing_event:
            return {"status": "already_processed", "idempotency_key": event.idempotency_key}

        # Record webhook event
        event_record = {
            "provider": "resend",
            "event_type": event.event_type.value,
            "idempotency_key": event.idempotency_key,
            "external_id": event.external_message_id,
            "payload": event.raw_payload,
            "processing_status": "processing",
            "received_at": now,
        }
        await db.integration_webhook_events.insert_one(event_record)

        # 2. Match Outbox item by provider_message_id
        outbox_doc = await db.email_outbox.find_one({"provider_message_id": event.external_message_id})

        # Map event type to Outbox status
        status_map = {
            CommunicationEventType.DELIVERED: OutboxStatus.DELIVERED,
            CommunicationEventType.BOUNCED: OutboxStatus.BOUNCED,
            CommunicationEventType.COMPLAINED: OutboxStatus.COMPLAINED,
            CommunicationEventType.OPENED: OutboxStatus.OPENED,
            CommunicationEventType.CLICKED: OutboxStatus.CLICKED,
            CommunicationEventType.FAILED: OutboxStatus.FAILED,
        }

        new_status = status_map.get(event.event_type)
        if outbox_doc and new_status:
            update_fields: Dict[str, Any] = {
                "status": new_status.value,
                "updated_at": now,
            }
            if new_status == OutboxStatus.DELIVERED:
                update_fields["delivered_at"] = now
            elif new_status == OutboxStatus.OPENED:
                update_fields["opened_at"] = now
            elif new_status == OutboxStatus.CLICKED:
                update_fields["clicked_at"] = now

            await db.email_outbox.update_one({"_id": outbox_doc["_id"]}, {"$set": update_fields})

            # Append activity to CRM if enquiry_id exists and event is meaningful
            enquiry_id = outbox_doc.get("enquiry_id")
            if enquiry_id and new_status in (OutboxStatus.DELIVERED, OutboxStatus.BOUNCED, OutboxStatus.OPENED):
                desc_map = {
                    OutboxStatus.DELIVERED: ("Email Delivered", f"Delivered to recipient ({outbox_doc.get('recipient_email')})"),
                    OutboxStatus.BOUNCED: ("Email Bounced", f"Delivery failed/bounced for {outbox_doc.get('recipient_email')}"),
                    OutboxStatus.OPENED: ("Email Opened", f"Opened by recipient ({outbox_doc.get('recipient_email')})"),
                }
                title, summary = desc_map[new_status]
                activity = EnquiryActivity(
                    type=f"email_{new_status.value}",
                    title=title,
                    summary=summary,
                    source="system",
                    metadata={"provider": "resend", "external_id": event.external_message_id},
                )
                await db.enquiries.update_one(
                    {"_id": enquiry_id},
                    {"$push": {"activities": activity.model_dump()}}
                )

        # Mark event as processed
        await db.integration_webhook_events.update_one(
            {"idempotency_key": event.idempotency_key},
            {"$set": {"processing_status": "processed", "processed_at": now}}
        )

        return {
            "status": "processed",
            "event_type": event.event_type.value,
            "idempotency_key": event.idempotency_key,
        }
