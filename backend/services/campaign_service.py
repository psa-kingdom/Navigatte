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
    def is_email_excluded(email: str, exclusions: List[str]) -> bool:
        """Checks if an email matches any explicit email or domain exclusions (e.g. '@navigatte.com')."""
        if not exclusions:
            return False
        clean_email = email.lower().strip()
        for excl in exclusions:
            clean_excl = excl.lower().strip()
            if not clean_excl:
                continue
            if clean_excl.startswith("@") and clean_email.endswith(clean_excl):
                return True
            if clean_excl.startswith("*@") and clean_email.endswith(clean_excl[1:]):
                return True
            if clean_email == clean_excl:
                return True
        return False

    @classmethod
    async def resolve_recipients(
        cls,
        db: AsyncIOMotorDatabase,
        campaign: CampaignModel,
    ) -> Dict[str, Any]:
        """Calculates raw, suppressed, excluded, and final deliverable recipients for a campaign."""
        if campaign.environment == "test":
            # Test Mode: HARD SAFETY BOUNDARY — strictly uses configured test_recipients
            test_list = [e.lower().strip() for e in campaign.test_recipients if e.strip()]
            return {
                "raw_count": len(test_list),
                "suppressed_count": 0,
                "excluded_count": 0,
                "final_count": len(test_list),
                "recipients": [{"email": e, "name": "Test Recipient", "vars": {"name": "Test Recipient", "email": e}} for e in test_list],
            }

        # Production Mode: Gather candidates from selected source
        candidate_contacts: Dict[str, Dict[str, Any]] = {}

        # 1. Audience contacts
        if campaign.audience_id:
            aud_contacts = await db.audience_contacts.find(
                {"audience_id": campaign.audience_id, "is_suppressed": False}
            ).to_list(10000)
            for c in aud_contacts:
                em = c["email"].lower().strip()
                candidate_contacts[em] = {
                    "email": em,
                    "name": c.get("name") or "",
                    "company": c.get("company") or "",
                    "attributes": c.get("attributes", {}),
                }

        # 2. Manual contacts if 'manual' or 'both'
        if campaign.audience_source in ("manual", "both") or getattr(campaign, "manual_recipients", None):
            for raw_em in getattr(campaign, "manual_recipients", []):
                clean_em = raw_em.lower().strip()
                if clean_em and clean_em not in candidate_contacts:
                    candidate_contacts[clean_em] = {
                        "email": clean_em,
                        "name": "",
                        "company": "",
                        "attributes": {},
                    }

        raw_count = len(candidate_contacts)

        # 3. Global Suppression Check
        suppression_emails = set(await db.email_suppressions.distinct("email"))
        unsuppressed = {
            em: data for em, data in candidate_contacts.items() if em not in suppression_emails
        }
        suppressed_count = raw_count - len(unsuppressed)

        # 4. Campaign-Specific Exclusions Check
        exclusions = campaign.exclusions or []
        final_recipients = []
        excluded_count = 0

        for em, data in unsuppressed.items():
            if cls.is_email_excluded(em, exclusions):
                excluded_count += 1
            else:
                final_recipients.append({
                    "email": em,
                    "name": data.get("name") or "Valued Client",
                    "vars": {
                        "name": data.get("name") or "Valued Client",
                        "company": data.get("company") or "",
                        "email": em,
                        **data.get("attributes", {}),
                    },
                })

        return {
            "raw_count": raw_count,
            "suppressed_count": suppressed_count,
            "excluded_count": excluded_count,
            "final_count": len(final_recipients),
            "recipients": final_recipients,
        }

    @classmethod
    async def validate_launch_checklist(
        cls,
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

        # 3. Template / Content validation
        has_custom_html = bool(getattr(campaign, "custom_html", None))
        template_valid = False
        if campaign.template_key and campaign.template_key != "custom":
            template = await db.email_templates.find_one({"key": campaign.template_key, "is_active": True})
            template_valid = bool(template)
        elif has_custom_html:
            template_valid = True

        if not template_valid and not has_custom_html:
            errors.append(f"Active template '{campaign.template_key}' or authored HTML content was not found.")

        # 4. Subject Line
        if not campaign.subject or not campaign.subject.strip():
            errors.append("Campaign email subject line is required.")

        # 5. Audience and Recipients validation
        rec_calc = await cls.resolve_recipients(db, campaign)
        final_count = rec_calc["final_count"]

        if campaign.environment == "test":
            if final_count == 0:
                errors.append("Test environment requires at least one configured test recipient.")
        else:
            if final_count == 0:
                errors.append("Production audience contains 0 deliverable contacts after exclusions and suppression.")

        checklist = {
            "environment_confirmed": env_match,
            "environment": campaign.environment,
            "provider_healthy": provider_enabled,
            "template_active": template_valid or has_custom_html,
            "template_key": campaign.template_key,
            "raw_recipients_count": rec_calc["raw_count"],
            "suppressed_recipients_count": rec_calc["suppressed_count"],
            "excluded_recipients_count": rec_calc["excluded_count"],
            "target_recipients_count": final_count,
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
            await db.campaigns.update_one(
                {"_id": campaign.id},
                {"$set": {"launch_checklist": checklist, "updated_at": datetime.now(timezone.utc)}}
            )
            raise ValueError(f"Launch checklist validation failed: {'; '.join(errors)}")

        now = datetime.now(timezone.utc)
        tpl_doc = await db.email_templates.find_one({"key": campaign.template_key}) if campaign.template_key != "custom" else None
        tpl = EmailTemplateModel.from_mongo(tpl_doc) if tpl_doc else None

        # Resolve recipients
        rec_calc = await self.resolve_recipients(db, campaign)
        recipients_to_queue = rec_calc["recipients"]

        # Authored content or template
        base_subject = campaign.subject or (tpl.subject if tpl else "Navigatte Communication")
        base_html = getattr(campaign, "custom_html", None) or (tpl.body_html if tpl else "<p>Navigatte Advisory</p>")
        base_text = (tpl.body_text if tpl else None)

        # Generate Outbox Items
        outbox_items = []
        from_email = campaign.sender_email or getattr(settings, "RESEND_FROM_EMAIL", "Navigatte <updates@updates.navigatte.com>")

        for rec in recipients_to_queue:
            rendered_subject = CommunicationsService.render_template(base_subject, rec["vars"])
            rendered_html = CommunicationsService.render_template(base_html, rec["vars"])
            rendered_text = CommunicationsService.render_template(base_text or "", rec["vars"]) if base_text else None

            tags = {"campaign_id": campaign.id}
            if campaign.template_key:
                tags["template_key"] = campaign.template_key

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
                tags=tags,
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
                "environment": campaign.environment,
            },
        )
        await db.communications_audit_logs.insert_one(audit.to_mongo())

        return campaign

