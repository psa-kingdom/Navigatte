"""EMS Campaign Domain Service.

Handles campaign validation checklists, environment isolation safety boundaries,
audience resolution with global suppression filtering, template version freezing,
unresolved variable detection, and durable outbox batch generation.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import settings
from models.audit import CommunicationsAuditLogModel
from models.campaign import CampaignModel, CampaignStatus
from models.communications import EmailTemplateModel, OutboxItemModel, OutboxStatus
from services.communications_service import CommunicationsService

logger = logging.getLogger(__name__)


class CampaignService:
    """Enterprise domain service managing the full EMS campaign lifecycle."""

    @staticmethod
    def is_email_excluded(email: str, exclusions: List[str]) -> bool:
        """Checks if an email matches any explicit email or domain exclusion (e.g. '@navigatte.com')."""
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

    @staticmethod
    def validate_unresolved_variables(rendered_html: str, rendered_subject: str = "") -> List[str]:
        """Scans rendered email content for any remaining {{ var }} placeholders.
        
        Used as a pre-launch validation step.
        - Production launches FAIL if any unresolved variables are found.
        - Test launches emit WARNINGS only.
        
        Returns:
            List of unresolved variable names found in the content.
        """
        pattern = r"\{\{\s*(\w+)\s*\}\}"
        found_html = re.findall(pattern, rendered_html)
        found_subject = re.findall(pattern, rendered_subject)
        return list(set(found_html + found_subject))

    @classmethod
    async def resolve_recipients(
        cls,
        db: AsyncIOMotorDatabase,
        campaign: CampaignModel,
    ) -> Dict[str, Any]:
        """Calculates raw, suppressed, excluded, and final deliverable recipients.
        
        In test mode: HARD SAFETY BOUNDARY — only test_recipients, never audience contacts.
        In production mode: audience + manual recipients, minus suppressed and excluded.
        
        Returns a dict including:
            raw_count, suppressed_count, excluded_count, final_count,
            audience_count, manual_additions_count, recipients (list of dicts)
        """
        if campaign.environment == "test":
            # Test Mode: HARD SAFETY BOUNDARY
            # Under NO circumstances are audience contacts used for test dispatch.
            # Only explicit test_recipients are valid targets.
            test_list = [e.lower().strip() for e in (campaign.test_recipients or []) if e.strip()]
            return {
                "raw_count": len(test_list),
                "audience_count": 0,
                "manual_additions_count": 0,
                "suppressed_count": 0,
                "excluded_count": 0,
                "final_count": len(test_list),
                "recipients": [
                    {
                        "email": e,
                        "name": "Test Recipient",
                        "vars": {
                            "name": "Test Recipient",
                            "email": e,
                            "company": "Navigatte Test",
                            "service_interest": "Platform Testing",
                            "unsubscribe_url": CommunicationsService.build_unsubscribe_url(e),
                        },
                    }
                    for e in test_list
                ],
            }

        # Production Mode: gather candidates from selected source(s)
        candidate_contacts: Dict[str, Dict[str, Any]] = {}
        audience_emails: set = set()

        # 1. Audience contacts (if audience_source includes audience)
        if campaign.audience_id and campaign.audience_source in ("audience", "both"):
            aud_contacts = await db.audience_contacts.find(
                {"audience_id": campaign.audience_id, "is_suppressed": False}
            ).to_list(10000)
            for c in aud_contacts:
                em = c["email"].lower().strip()
                audience_emails.add(em)
                candidate_contacts[em] = {
                    "email": em,
                    "name": c.get("name") or "",
                    "company": c.get("company") or "",
                    "attributes": c.get("attributes", {}),
                }

        audience_count = len(audience_emails)

        # 2. Manual contacts (if audience_source includes manual)
        manual_additions_count = 0
        if campaign.audience_source in ("manual", "both"):
            for raw_em in getattr(campaign, "manual_recipients", []):
                clean_em = raw_em.lower().strip()
                if clean_em and clean_em not in candidate_contacts:
                    candidate_contacts[clean_em] = {
                        "email": clean_em,
                        "name": "",
                        "company": "",
                        "attributes": {},
                    }
                    manual_additions_count += 1

        raw_count = len(candidate_contacts)

        # 3. Global Suppression filter (re-check at launch time for freshness)
        suppression_emails = set(await db.email_suppressions.distinct("email"))
        unsuppressed = {
            em: data for em, data in candidate_contacts.items()
            if em not in suppression_emails
        }
        suppressed_count = raw_count - len(unsuppressed)

        # 4. Campaign-specific exclusion filter
        exclusions = campaign.exclusions or []
        final_recipients: List[Dict[str, Any]] = []
        excluded_count = 0

        for em, data in unsuppressed.items():
            if cls.is_email_excluded(em, exclusions):
                excluded_count += 1
            else:
                # Build variables for this recipient, including signed unsubscribe URL
                unsubscribe_url = CommunicationsService.build_unsubscribe_url(em)
                final_recipients.append({
                    "email": em,
                    "name": data.get("name") or "Valued Client",
                    "vars": {
                        "name": data.get("name") or "Valued Client",
                        "company": data.get("company") or "",
                        "email": em,
                        "unsubscribe_url": unsubscribe_url,
                        **data.get("attributes", {}),
                    },
                })

        return {
            "raw_count": raw_count,
            "audience_count": audience_count,
            "manual_additions_count": manual_additions_count,
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
        warnings: List[str] = []
        now = datetime.now(timezone.utc)

        # 1. Environment check
        current_env = getattr(settings, "COMMUNICATIONS_ENVIRONMENT", "test")
        env_match = (campaign.environment == current_env)
        if not env_match:
            errors.append(
                f"Campaign environment '{campaign.environment}' does not match system "
                f"environment '{current_env}'. Update campaign or system environment."
            )

        # 2. Provider health
        provider_enabled = settings.RESEND_ENABLED
        if not provider_enabled:
            errors.append("Provider is not configured or disabled (RESEND_API_KEY missing).")

        # 3. Template / Content validation
        has_custom_html = bool(getattr(campaign, "custom_html", None))
        template_valid = False
        resolved_template_version: Optional[int] = None

        if campaign.template_key and campaign.template_key != "custom":
            template = await db.email_templates.find_one({"key": campaign.template_key, "is_active": True})
            template_valid = bool(template)
            if template:
                resolved_template_version = template.get("version", 1)
        elif has_custom_html:
            template_valid = True

        if not template_valid and not has_custom_html:
            errors.append(
                f"Active template '{campaign.template_key}' not found or no custom HTML authored."
            )

        # 4. Subject Line
        if not campaign.subject or not campaign.subject.strip():
            errors.append("Campaign email subject line is required.")

        # 5. Recipient Resolution
        rec_calc = await cls.resolve_recipients(db, campaign)
        final_count = rec_calc["final_count"]

        if campaign.environment == "test":
            if final_count == 0:
                errors.append(
                    "Test mode requires at least one configured test_recipient on the campaign."
                )
        else:
            if final_count == 0:
                errors.append(
                    "Production audience has 0 deliverable contacts after suppression and exclusions."
                )

        # 6. Unresolved variable check (pre-flight render with sample vars)
        if template_valid or has_custom_html:
            sample_vars = {
                "name": "Test User",
                "email": "test@example.com",
                "company": "Test Corp",
                "unsubscribe_url": "https://navigatte.com/unsubscribe",
            }
            try:
                snapshot = await CommunicationsService.render_message(
                    db,
                    template_key=campaign.template_key if not has_custom_html else None,
                    template_version=getattr(campaign, "template_version", None),
                    custom_html=getattr(campaign, "custom_html", None),
                    subject=campaign.subject,
                    variables=sample_vars,
                )
                if snapshot.unresolved_variables:
                    if campaign.environment == "production":
                        errors.append(
                            f"Unresolved template variables detected: "
                            f"{', '.join(snapshot.unresolved_variables)}. "
                            "These would appear literally in recipient emails."
                        )
                    else:
                        warnings.append(
                            f"Unresolved variables in template (non-blocking for test): "
                            f"{', '.join(snapshot.unresolved_variables)}"
                        )
            except Exception as e:
                warnings.append(f"Could not complete pre-flight render check: {e}")

        checklist = {
            "environment_confirmed": env_match,
            "environment": campaign.environment,
            "provider_healthy": provider_enabled,
            "template_active": template_valid or has_custom_html,
            "template_key": campaign.template_key,
            "template_version": resolved_template_version,
            "raw_recipients_count": rec_calc["raw_count"],
            "audience_count": rec_calc.get("audience_count", 0),
            "manual_additions_count": rec_calc.get("manual_additions_count", 0),
            "suppressed_recipients_count": rec_calc["suppressed_count"],
            "excluded_recipients_count": rec_calc["excluded_count"],
            "target_recipients_count": final_count,
            "warnings": warnings,
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
        """Validates launch checklist, freezes template version, and queues outbox batch."""
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
        from_email = campaign.sender_email or getattr(
            settings, "RESEND_FROM_EMAIL", "Navigatte <updates@updates.navigatte.com>"
        )

        # -----------------------------------------------------------------------
        # TEMPLATE VERSION FREEZE
        # Record the exact template version used at launch time. Future updates
        # to the master template will NOT affect outbox items for this campaign.
        # -----------------------------------------------------------------------
        frozen_template_version: Optional[int] = getattr(campaign, "template_version", None)
        if not frozen_template_version and campaign.template_key and campaign.template_key != "custom":
            tpl_doc = await db.email_templates.find_one({"key": campaign.template_key, "is_active": True})
            if tpl_doc:
                frozen_template_version = tpl_doc.get("version", 1)

        # Record frozen version on campaign record
        if frozen_template_version is not None:
            await db.campaigns.update_one(
                {"_id": campaign.id},
                {"$set": {"template_version": frozen_template_version}}
            )

        # -----------------------------------------------------------------------
        # RECIPIENT RESOLUTION
        # -----------------------------------------------------------------------
        rec_calc = await self.resolve_recipients(db, campaign)
        recipients_to_queue = rec_calc["recipients"]

        # -----------------------------------------------------------------------
        # OUTBOX ITEM GENERATION (using canonical render pipeline)
        # Each item stores the fully rendered content snapshot so that:
        # - The delivery worker doesn't need to re-query the template
        # - Template updates cannot alter queued content (integrity guaranteed)
        # -----------------------------------------------------------------------
        outbox_items = []

        for rec in recipients_to_queue:
            try:
                snapshot = await CommunicationsService.render_message(
                    db,
                    template_key=campaign.template_key if not getattr(campaign, "custom_html", None) else None,
                    template_version=frozen_template_version,
                    custom_html=getattr(campaign, "custom_html", None),
                    subject=campaign.subject,
                    variables=rec["vars"],
                )
            except Exception as e:
                logger.error(f"Render failed for {rec['email']} in campaign {campaign.id}: {e}")
                # Use unrendered content as fallback to not block the entire batch
                snapshot = type("Snapshot", (), {
                    "subject": campaign.subject or "Navigatte Communication",
                    "body_html": getattr(campaign, "custom_html", "") or "<p>Navigatte Communication</p>",
                    "body_text": None,
                })()

            tags = {"campaign_id": campaign.id}
            if campaign.template_key:
                tags["template_key"] = campaign.template_key

            item = OutboxItemModel(
                idempotency_key=f"campaign:{campaign.id}:{rec['email']}",
                template_key=campaign.template_key,
                recipient_email=rec["email"],
                recipient_name=rec["name"],
                subject=snapshot.subject,
                body_html=snapshot.body_html,
                body_text=getattr(snapshot, "body_text", None),
                from_email=from_email,
                status=OutboxStatus.QUEUED,
                provider="resend",
                environment=campaign.environment,
                tags=tags,
                metadata={
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "template_version": frozen_template_version,
                },
            )
            outbox_items.append(item.to_mongo())

        if outbox_items:
            # insert_many with ordered=False continues on duplicate key errors
            try:
                await db.email_outbox.insert_many(outbox_items, ordered=False)
            except Exception as e:
                logger.warning(f"Some outbox items may be duplicates (idempotency): {e}")

        # Update campaign to SENDING state
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
                "template_version": frozen_template_version,
                "updated_at": campaign.updated_at,
            }}
        )

        # Audit log
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
                "template_version": frozen_template_version,
                "environment": campaign.environment,
            },
        )
        await db.communications_audit_logs.insert_one(audit.to_mongo())
        logger.info(
            f"[CampaignService] Campaign '{campaign.name}' launched: "
            f"{len(outbox_items)} outbox items queued (template v{frozen_template_version})."
        )

        return campaign
