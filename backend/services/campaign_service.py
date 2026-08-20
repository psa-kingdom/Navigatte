"""EMS Campaign Domain Service.

Handles campaign validation checklists, environment isolation safety boundaries,
audience resolution with global suppression filtering, and outbox batch generation.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import settings
from models.audit import CommunicationsAuditLogModel
from models.audience import AudienceModel, SuppressionRecordModel
from models.campaign import CampaignModel, CampaignStatus
from models.communications import EmailTemplateModel, OutboxItemModel, OutboxStatus
from services.communications_service import CommunicationsService

logger = logging.getLogger(__name__)


class CampaignService:
    """Enterprise domain service managing the full EMS campaign lifecycle."""

    @staticmethod
    async def validate_launch_checklist(
        db: AsyncIOMotorDatabase,
        campaign: CampaignModel,
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Evaluates launch prerequisites and returns (is_valid, checklist_dict, error_messages)."""
        errors: List[str] = []
        now = datetime.now(timezone.utc)

        # 1. Environment check
        current_env = getattr(settings, "COMMUNICATIONS_ENVIRONMENT", "test")
        env_match = (campaign.environment == current_env)
        if not env_match:
            errors.append(f"Campaign environment '{campaign.environment}' does not match system environment '{current_env}'.")

        # 2. Provider health
        provider_enabled = settings.RESEND_ENABLED
        if not provider_enabled:
            errors.append("Provider is not configured or disabled (RESEND_API_KEY missing).")

        # 3. Template validation
        template = await db.email_templates.find_one({"key": campaign.template_key, "is_active": True})
        template_valid = bool(template)
        if not template_valid:
            errors.append(f"Active template '{campaign.template_key}' was not found.")

        # 4. Audience and Recipients validation
        target_count = 0
        suppressed_count = 0
        if campaign.environment == "test":
            # Test mode: only uses test_recipients
            if not campaign.test_recipients:
                errors.append("Test environment requires at least one test recipient.")
            target_count = len(campaign.test_recipients)
        else:
            # Production mode: validates audience
            if not campaign.audience_id:
                errors.append("Production campaign requires a target audience.")
            else:
                aud = await db.audiences.find_one({"_id": campaign.audience_id})
                if not aud:
                    errors.append(f"Target audience '{campaign.audience_id}' not found.")
                else:
                    raw_contacts = await db.audience_contacts.find(
                        {"audience_id": campaign.audience_id, "is_suppressed": False}
                    ).to_list(10000)

                    # Check global suppression
                    suppression_emails = set(
                        await db.email_suppressions.distinct("email")
                    )
                    eligible_contacts = [
                        c for c in raw_contacts if c["email"].lower().strip() not in suppression_emails
                    ]
                    target_count = len(eligible_contacts)
                    suppressed_count = len(raw_contacts) - target_count

                    if target_count == 0:
                        errors.append("Audience contains 0 deliverable contacts after suppression filtering.")

        checklist = {
            "environment_confirmed": env_match,
            "environment": campaign.environment,
            "provider_healthy": provider_enabled,
            "template_active": template_valid,
            "template_key": campaign.template_key,
            "target_recipients_count": target_count,
            "suppressed_recipients_count": suppressed_count,
            "has_blocking_errors": len(errors) > 0,
            "validated_at": now.isoformat(),
        }

        is_valid = (len(errors) == 0)
        return is_valid, checklist, errors

    async def launch_campaign(
        self,
        db: AsyncIOMotorDatabase,
        campaign_id: str,
        actor_email: str = "admin@navigatte.com",
    ) -> CampaignModel:
        """Executes validation and dispatches campaign into durable outbox."""
        doc = await db.campaigns.find_one({"_id": campaign_id})
        if not doc:
            raise ValueError(f"Campaign '{campaign_id}' not found.")

        campaign = CampaignModel.from_mongo(doc)

        if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.READY, CampaignStatus.PAUSED):
            raise ValueError(f"Cannot launch campaign in '{campaign.status.value}' state.")

        # Evaluate launch checklist
        is_valid, checklist, errors = await self.validate_launch_checklist(db, campaign)
        if not is_valid:
            # Record checklist failure
            await db.campaigns.update_one(
                {"_id": campaign.id},
                {"$set": {"launch_checklist": checklist, "updated_at": datetime.now(timezone.utc)}}
            )
            raise ValueError(f"Launch checklist validation failed: {'; '.join(errors)}")

        now = datetime.now(timezone.utc)
        tpl_doc = await db.email_templates.find_one({"key": campaign.template_key})
        tpl = EmailTemplateModel.from_mongo(tpl_doc) if tpl_doc else None

        # Resolve recipients based on environment safety boundary
        recipients_to_queue: List[Dict[str, Any]] = []

        if campaign.environment == "test":
            # HARD BOUNDARY: Test mode ONLY sends to explicit test_recipients
            for email in campaign.test_recipients:
                recipients_to_queue.append({
                    "email": email,
                    "name": "Test Recipient",
                    "vars": {"name": "Test Recipient", "email": email},
                })
        else:
            # Production mode: query audience contacts minus suppression
            suppression_emails = set(await db.email_suppressions.distinct("email"))
            contacts = await db.audience_contacts.find(
                {"audience_id": campaign.audience_id, "is_suppressed": False}
            ).to_list(10000)

            for contact in contacts:
                clean_email = contact["email"].lower().strip()
                if clean_email not in suppression_emails:
                    recipients_to_queue.append({
                        "email": clean_email,
                        "name": contact.get("name", ""),
                        "vars": {
                            "name": contact.get("name") or "Valued Client",
                            "company": contact.get("company") or "",
                            **contact.get("attributes", {}),
                        },
                    })

        # Generate Outbox Items
        outbox_items = []
        from_email = campaign.sender_email or getattr(settings, "RESEND_FROM_EMAIL", "Navigatte <updates@updates.navigatte.com>")

        for rec in recipients_to_queue:
            rendered_subject = CommunicationsService.render_template(campaign.subject or tpl.subject, rec["vars"]) if tpl else campaign.subject
            rendered_html = CommunicationsService.render_template(tpl.body_html, rec["vars"]) if tpl else f"<p>Campaign {campaign.name}</p>"
            rendered_text = CommunicationsService.render_template(tpl.body_text or "", rec["vars"]) if (tpl and tpl.body_text) else None

            item = OutboxItemModel(
                idempotency_key=f"campaign:{campaign.id}:{rec['email']}",
                template_key=campaign.template_key,
                recipient_email=rec["email"],
                recipient_name=rec["name"],
                subject=rendered_subject,
                body_html=rendered_html,
                body_text=rendered_text,
                from_email=from_email,
                status=OutboxStatus.QUEUED,
                provider="resend",
                environment=campaign.environment,
                tags={"campaign_id": campaign.id, "template_key": campaign.template_key},
                metadata={"campaign_id": campaign.id, "campaign_name": campaign.name},
            )
            outbox_items.append(item.to_mongo())

        if outbox_items:
            await db.email_outbox.insert_many(outbox_items)

        # Update Campaign State
        campaign.status = CampaignStatus.SENDING
        campaign.total_recipients = len(outbox_items)
        campaign.launched_at = now
        campaign.launch_checklist = checklist
        campaign.updated_at = now

        await db.campaigns.update_one(
            {"_id": campaign.id},
            {"$set": {
                "status": campaign.status.value,
                "total_recipients": campaign.total_recipients,
                "launched_at": campaign.launched_at,
                "launch_checklist": campaign.launch_checklist,
                "updated_at": campaign.updated_at,
            }}
        )

        # Write Audit Log
        audit = CommunicationsAuditLogModel(
            actor_email=actor_email,
            action="campaign_launched",
            target_type="campaign",
            target_id=campaign.id,
            environment=campaign.environment,
            details={
                "campaign_name": campaign.name,
                "recipients_count": len(outbox_items),
                "template_key": campaign.template_key,
            },
        )
        await db.communications_audit_logs.insert_one(audit.to_mongo())

        return campaign
