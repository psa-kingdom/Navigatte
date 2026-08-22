"""Communications and Transactional Email Engine Service.

Handles template management, canonical message rendering, idempotent outbox storage,
Resend dispatch, delivery webhook tracking with CRM timeline correlation,
automatic bounce/complaint suppression, and signed unsubscribe tokens.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import html
import logging
import re
import time
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
            "<p style='color: #666; font-size: 12px; margin-top: 30px;'>Navigatte Consultancy &amp; Platforms</p>"
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


@dataclass
class RenderedMessageSnapshot:
    """Immutable content snapshot produced by the canonical render pipeline.
    
    This is the single source of truth for all email content — preview,
    test-send, and campaign launch all use this exact structure.
    Preview shown == outbox stored == email sent. No drift possible.
    """
    subject: str
    body_html: str
    body_text: Optional[str]
    template_key: Optional[str]
    template_version: Optional[int]
    from_email: str
    variables_used: Dict[str, Any]
    unresolved_variables: List[str]  # Any {{ var }} still present after render


def _get_unsubscribe_secret() -> bytes:
    """Returns the HMAC secret for unsubscribe token signing."""
    secret = getattr(settings, "UNSUBSCRIBE_SECRET", None) or getattr(settings, "_raw_jwt_secret", None)
    if not secret:
        logger.warning(
            "UNSUBSCRIBE_SECRET is not set. Falling back to JWT_SECRET for unsubscribe token signing. "
            "Set UNSUBSCRIBE_SECRET in environment variables for production use."
        )
        secret = "navigatte_unsub_dev_key_fallback"
    return secret.encode("utf-8")


class CommunicationsService:
    def __init__(self, provider: Optional[ResendCommunicationsProvider] = None):
        self.provider = provider or ResendCommunicationsProvider()

    # =========================================================================
    # TEMPLATE MANAGEMENT
    # =========================================================================

    @staticmethod
    async def ensure_default_templates(db: AsyncIOMotorDatabase):
        """Seeds default email templates if they do not exist."""
        for tpl_data in DEFAULT_TEMPLATES:
            existing = await db.email_templates.find_one({"key": tpl_data["key"]})
            if not existing:
                tpl = EmailTemplateModel(**tpl_data, is_system=True, category="system")
                await db.email_templates.insert_one(tpl.to_mongo())
                logger.info(f"Seeded default email template: {tpl.key}")

    # =========================================================================
    # CANONICAL RENDER PIPELINE (The core architectural invariant)
    # =========================================================================

    @staticmethod
    def html_escape_variables(variables: Dict[str, Any]) -> Dict[str, Any]:
        """Escapes all variable values before HTML body interpolation.
        
        Prevents HTML injection from user-submitted content (e.g. contact form
        name/company fields containing script tags or HTML entities).
        Subject lines are NOT escaped here (plain text field).
        """
        return {k: html.escape(str(v)) if isinstance(v, str) else v for k, v in variables.items()}

    @staticmethod
    def render_template(body: str, variables: Dict[str, Any]) -> str:
        """Safely interpolates {{ variable }} placeholders."""
        rendered = body
        for key, val in variables.items():
            placeholder = r"\{\{\s*" + re.escape(key) + r"\s*\}\}"
            rendered = re.sub(placeholder, str(val), rendered)
        return rendered

    @staticmethod
    def detect_unresolved_variables(rendered_content: str) -> List[str]:
        """Finds any {{ var }} placeholders remaining after template rendering."""
        pattern = r"\{\{\s*(\w+)\s*\}\}"
        return list(set(re.findall(pattern, rendered_content)))

    @staticmethod
    async def render_message(
        db: AsyncIOMotorDatabase,
        *,
        template_key: Optional[str] = None,
        template_version: Optional[int] = None,
        custom_html: Optional[str] = None,
        subject: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        escape_html_in_variables: bool = True,
    ) -> RenderedMessageSnapshot:
        """THE canonical render pipeline. One function for all email content.
        
        This is the architectural invariant that ensures:
            preview == test-send == outbox snapshot == delivered email
        
        Args:
            db: Database connection
            template_key: Navigatte template slug (e.g. 'enquiry_acknowledgement')
            template_version: Specific version to use (None = active/latest)
            custom_html: Raw HTML body (overrides template if provided)
            subject: Email subject line (overrides template subject if provided)
            variables: Template variables for substitution
            escape_html_in_variables: Whether to HTML-escape variable values before body substitution
            
        Returns:
            RenderedMessageSnapshot with fully resolved subject, body_html, body_text,
            template reference, and list of any unresolved {{ var }} placeholders.
        """
        vars_dict = variables or {}
        from_email = getattr(settings, "RESEND_FROM_EMAIL", "Navigatte <updates@updates.navigatte.com>")

        # Resolve content source: custom_html takes priority over template
        raw_subject: str = subject or "Navigatte Communication"
        raw_html: str = ""
        raw_text: Optional[str] = None
        resolved_template_key: Optional[str] = template_key
        resolved_template_version: Optional[int] = template_version

        if custom_html:
            # Custom HTML mode: use exactly what was provided
            raw_html = custom_html
            if not subject:
                raw_subject = "Navigatte Communication"
            resolved_template_key = "custom"
            resolved_template_version = None

        elif template_key and template_key != "custom":
            # Template mode: load from DB
            tpl_doc = None

            if template_version is not None:
                # Load specific historical version snapshot
                from models.template_version import EmailTemplateVersionModel
                v_doc = await db.email_template_versions.find_one(
                    {"template_key": template_key, "version": template_version}
                )
                if v_doc:
                    raw_html = v_doc.get("body_html", "")
                    raw_text = v_doc.get("body_text")
                    if not subject:
                        raw_subject = v_doc.get("subject", raw_subject)
                    resolved_template_version = template_version
                else:
                    # Fall back to active template
                    logger.warning(
                        f"Template version {template_key}@v{template_version} not found, "
                        "falling back to active version."
                    )
                    tpl_doc = await db.email_templates.find_one({"key": template_key, "is_active": True})
            else:
                tpl_doc = await db.email_templates.find_one({"key": template_key, "is_active": True})

            if tpl_doc:
                raw_html = tpl_doc.get("body_html", "")
                raw_text = tpl_doc.get("body_text")
                if not subject:
                    raw_subject = tpl_doc.get("subject", raw_subject)
                resolved_template_version = tpl_doc.get("version", 1)

        else:
            # No content provided — use minimal fallback
            raw_html = "<p>Navigatte Communication</p>"

        # Escape variable values before HTML interpolation (security)
        html_vars = CommunicationsService.html_escape_variables(vars_dict) if escape_html_in_variables else vars_dict
        # Subject uses unescaped variables (plain text)
        text_vars = vars_dict

        # Render subject (plain text — no escaping)
        rendered_subject = CommunicationsService.render_template(raw_subject, text_vars)

        # Render HTML body (escaped variables)
        rendered_html = CommunicationsService.render_template(raw_html, html_vars)

        # Render text body
        rendered_text = CommunicationsService.render_template(raw_text, text_vars) if raw_text else None

        # Detect any remaining unresolved placeholders
        unresolved = CommunicationsService.detect_unresolved_variables(rendered_html)
        if rendered_text:
            unresolved += CommunicationsService.detect_unresolved_variables(rendered_text)
        unresolved = list(set(unresolved))

        return RenderedMessageSnapshot(
            subject=rendered_subject,
            body_html=rendered_html,
            body_text=rendered_text,
            template_key=resolved_template_key,
            template_version=resolved_template_version,
            from_email=from_email,
            variables_used=vars_dict,
            unresolved_variables=unresolved,
        )

    # =========================================================================
    # UNSUBSCRIBE TOKEN GENERATION
    # =========================================================================

    @staticmethod
    def generate_unsubscribe_token(email: str, expiry_days: int = 30) -> Tuple[str, int]:
        """Generates a signed HMAC-SHA256 unsubscribe token with expiry.
        
        Returns:
            (token_hex, expires_at_unix_timestamp)
        """
        expires_at = int(time.time()) + (expiry_days * 86400)
        message = f"{email.lower().strip()}:{expires_at}".encode("utf-8")
        secret = _get_unsubscribe_secret()
        token = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return token, expires_at

    @staticmethod
    def verify_unsubscribe_token(email: str, token: str, expires_at: int) -> bool:
        """Validates an unsubscribe token. Returns True if valid and not expired."""
        if int(time.time()) > expires_at:
            return False
        message = f"{email.lower().strip()}:{expires_at}".encode("utf-8")
        secret = _get_unsubscribe_secret()
        expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, token)

    @staticmethod
    def build_unsubscribe_url(email: str, base_url: Optional[str] = None) -> str:
        """Builds a signed unsubscribe URL for use in email templates."""
        import urllib.parse
        token, expires_at = CommunicationsService.generate_unsubscribe_token(email)
        base = base_url or "https://navigatte.com"
        params = urllib.parse.urlencode({
            "email": email.lower().strip(),
            "token": token,
            "exp": expires_at,
        })
        return f"{base}/api/unsubscribe?{params}"

    # =========================================================================
    # ERROR CLASSIFICATION
    # =========================================================================

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

    # =========================================================================
    # TRANSACTIONAL EMAIL DISPATCH (uses canonical render pipeline)
    # =========================================================================

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
        custom_html: Optional[str] = None,
    ) -> OutboxItemModel:
        """Queues, logs, and dispatches a transactional email through the configured provider.
        
        Uses the canonical render pipeline to ensure preview == outbox == sent.
        """
        vars_dict = variables or {}
        now = datetime.now(timezone.utc)
        idem_key = idempotency_key or f"email:{template_key}:{recipient_email}:{int(now.timestamp())}"

        # 1. Check idempotency in outbox
        existing = await db.email_outbox.find_one({"idempotency_key": idem_key})
        if existing:
            logger.info(f"Email with idempotency key '{idem_key}' already processed.")
            return OutboxItemModel.from_mongo(existing)

        # 2. Use canonical render pipeline
        snapshot = await self.render_message(
            db,
            template_key=template_key if not custom_html else None,
            custom_html=custom_html,
            subject=custom_subject,
            variables=vars_dict,
        )

        environment = getattr(settings, "COMMUNICATIONS_ENVIRONMENT", "test")

        # 3. Create Outbox Item (initial status SENDING)
        outbox_item = OutboxItemModel(
            idempotency_key=idem_key,
            template_key=snapshot.template_key or template_key,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=snapshot.subject,
            body_html=snapshot.body_html,
            body_text=snapshot.body_text,
            from_email=snapshot.from_email,
            status=OutboxStatus.SENDING,
            provider=self.provider.name,
            enquiry_id=enquiry_id,
            attempt_count=1,
            environment=environment,
            metadata={
                **vars_dict,
                "template_version": snapshot.template_version,
            },
        )
        await db.email_outbox.insert_one(outbox_item.to_mongo())

        # 4. Dispatch via Provider
        tags = {"template_key": snapshot.template_key or template_key or "custom"}
        if enquiry_id:
            tags["enquiry_id"] = str(enquiry_id)

        msg = EmailMessage(
            to=[EmailRecipient(email=recipient_email, name=recipient_name)],
            subject=snapshot.subject,
            html_body=snapshot.body_html,
            text_body=snapshot.body_text,
            from_email=snapshot.from_email,
            idempotency_key=idem_key,
            tags=tags,
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
                summary=f"Transactional email sent: '{snapshot.subject}' to {recipient_email}",
                source="system",
                metadata={"template_key": template_key, "provider_message_id": result.message_id},
            )
            await db.enquiries.update_one(
                {"_id": enquiry_id},
                {"$push": {"activities": activity.model_dump()}}
            )

        return outbox_item

    # =========================================================================
    # RETRY
    # =========================================================================

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

        tags = {"template_key": outbox_item.template_key or "custom"}
        if outbox_item.enquiry_id:
            tags["enquiry_id"] = str(outbox_item.enquiry_id)

        msg = EmailMessage(
            to=[EmailRecipient(email=outbox_item.recipient_email, name=outbox_item.recipient_name)],
            subject=outbox_item.subject,
            html_body=outbox_item.body_html,
            text_body=outbox_item.body_text,
            from_email=outbox_item.from_email,
            idempotency_key=f"{outbox_item.idempotency_key}:retry:{outbox_item.attempt_count + 1}",
            tags=tags,
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

    # =========================================================================
    # WEBHOOK PROCESSING (with automatic bounce/complaint suppression)
    # =========================================================================

    async def process_resend_webhook(
        self,
        db: AsyncIOMotorDatabase,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Processes inbound delivery tracking webhook from Resend (Svix).
        
        Automatically creates suppression records for bounce and complaint events.
        This closes the gap where bounced contacts would not be auto-suppressed.
        """
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
            elif new_status == OutboxStatus.BOUNCED:
                update_fields["bounced_at"] = now
            elif new_status == OutboxStatus.COMPLAINED:
                update_fields["complained_at"] = now

            await db.email_outbox.update_one({"_id": outbox_doc["_id"]}, {"$set": update_fields})

            # ---------------------------------------------------------------
            # AUTOMATIC BOUNCE/COMPLAINT SUPPRESSION
            # Closes the gap identified in the audit: bounced/complained emails
            # were NOT automatically added to email_suppressions.
            # ---------------------------------------------------------------
            recipient_email = outbox_doc.get("recipient_email", "").lower().strip()
            if recipient_email and new_status in (OutboxStatus.BOUNCED, OutboxStatus.COMPLAINED):
                reason = "hard_bounce" if new_status == OutboxStatus.BOUNCED else "complaint"
                await db.email_suppressions.update_one(
                    {"email": recipient_email},
                    {"$setOnInsert": {
                        "email": recipient_email,
                        "reason": reason,
                        "source": "resend_webhook",
                        "created_at": now,
                    }},
                    upsert=True,
                )
                # Mark all audience contacts with this email as suppressed
                await db.audience_contacts.update_many(
                    {"email": recipient_email},
                    {"$set": {"is_suppressed": True}}
                )
                logger.info(
                    f"[AutoSuppression] {reason} event for {recipient_email} → "
                    "added to email_suppressions."
                )

            # Append activity to CRM if enquiry_id exists
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
