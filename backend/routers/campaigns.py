"""EMS Campaigns Router.

Provides endpoints for campaign lifecycle management, launch validation,
status transitions, and telemetry metrics.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr

from core.database import get_database
from core.dependencies import get_current_admin
from models.admin import AdminUser
from models.audit import CommunicationsAuditLogModel
from models.campaign import CampaignModel, CampaignStatus
from services.campaign_service import CampaignService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/communications/campaigns", tags=["campaigns"])


class CampaignCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    environment: str = "test"  # 'test' | 'production'
    sender_email: Optional[str] = None
    reply_to: Optional[str] = None
    subject: str
    template_key: str = "custom"
    template_version: Optional[int] = None   # None = freeze active version at launch
    audience_id: Optional[str] = None
    audience_source: str = "audience"  # 'manual' | 'both' | 'audience'
    manual_recipients: List[str] = []
    exclusions: List[str] = []
    custom_html: Optional[str] = None
    test_recipients: List[EmailStr] = []


class CampaignUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    environment: Optional[str] = None
    sender_email: Optional[str] = None
    reply_to: Optional[str] = None
    subject: Optional[str] = None
    template_key: Optional[str] = None
    template_version: Optional[int] = None   # None = use active version at launch
    audience_id: Optional[str] = None
    audience_source: Optional[str] = None
    manual_recipients: Optional[List[str]] = None
    exclusions: Optional[List[str]] = None
    custom_html: Optional[str] = None
    test_recipients: Optional[List[EmailStr]] = None


@router.get("")
async def list_campaigns(
    environment: Optional[str] = Query(None, description="Filter by environment (test / production)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Lists EMS campaigns with status and environment filtering."""
    query: Dict[str, Any] = {}
    if environment:
        query["environment"] = environment
    if status:
        query["status"] = status

    total = await db.campaigns.count_documents(query)
    cursor = db.campaigns.find(query).sort("created_at", -1).limit(100)
    docs = await cursor.to_list(100)

    items = [CampaignModel.from_mongo(d).model_dump() for d in docs]
    return {"items": items, "total": total}


@router.post("")
async def create_campaign(
    payload: CampaignCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Creates a new campaign in DRAFT state."""
    now = datetime.now(timezone.utc)
    campaign = CampaignModel(
        name=payload.name,
        description=payload.description,
        environment=payload.environment,
        sender_email=payload.sender_email or "Navigatte <updates@updates.navigatte.com>",
        reply_to=payload.reply_to,
        subject=payload.subject,
        template_key=payload.template_key,
        audience_id=payload.audience_id,
        audience_source=payload.audience_source,
        manual_recipients=payload.manual_recipients,
        exclusions=payload.exclusions,
        custom_html=payload.custom_html,
        test_recipients=payload.test_recipients,
        status=CampaignStatus.DRAFT,
        created_by=admin.email,
        created_at=now,
        updated_at=now,
    )
    await db.campaigns.insert_one(campaign.to_mongo())

    # Write audit log
    audit = CommunicationsAuditLogModel(
        actor_email=admin.email,
        action="campaign_created",
        target_type="campaign",
        target_id=campaign.id,
        environment=campaign.environment,
        details={"name": campaign.name, "template_key": campaign.template_key},
    )
    await db.communications_audit_logs.insert_one(audit.to_mongo())

    return campaign.model_dump()


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Retrieves a single campaign with launch checklist and delivery metrics."""
    doc = await db.campaigns.find_one({"_id": campaign_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found.",
        )
    return CampaignModel.from_mongo(doc).model_dump()


@router.put("/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    payload: CampaignUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Updates an editable campaign draft."""
    doc = await db.campaigns.find_one({"_id": campaign_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    if doc.get("status") not in (CampaignStatus.DRAFT.value, CampaignStatus.READY.value, CampaignStatus.PAUSED.value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit a launched or completed campaign.")

    now = datetime.now(timezone.utc)
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    update_data["updated_at"] = now

    await db.campaigns.update_one({"_id": campaign_id}, {"$set": update_data})
    updated_doc = await db.campaigns.find_one({"_id": campaign_id})
    return CampaignModel.from_mongo(updated_doc).model_dump()


@router.post("/{campaign_id}/calculate-recipients")
async def calculate_campaign_recipients(
    campaign_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Calculates real-time net deliverable recipient count with exclusion and suppression breakdown."""
    doc = await db.campaigns.find_one({"_id": campaign_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    campaign = CampaignModel.from_mongo(doc)
    calc = await CampaignService.resolve_recipients(db, campaign)
    return {
        "raw_count": calc["raw_count"],
        "suppressed_count": calc["suppressed_count"],
        "excluded_count": calc["excluded_count"],
        "final_count": calc["final_count"],
    }


@router.get("/{campaign_id}/preview")
async def preview_campaign(
    campaign_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Renders preview of campaign subject and HTML body with sample variables."""
    doc = await db.campaigns.find_one({"_id": campaign_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    campaign = CampaignModel.from_mongo(doc)

    tpl_doc = await db.email_templates.find_one({"key": campaign.template_key}) if campaign.template_key != "custom" else None
    sample_vars = {
        "name": "Sarah Connor",
        "company": "Cyberdyne Systems",
        "email": "sarah@cyberdyne.io",
        "unsubscribe_url": "https://navigatte.com/unsubscribe?email=sarah@cyberdyne.io",
        "service_interest": "Enterprise Security Architecture",
        "start_time": "Aug 25, 2026, 2:00 PM UTC",
        "meeting_url": "https://navigatte.com/meet/demo",
    }

    base_subject = campaign.subject or (tpl_doc.get("subject") if tpl_doc else "Navigatte Communication")
    base_html = campaign.custom_html or (tpl_doc.get("body_html") if tpl_doc else "<p>Navigatte Campaign Content</p>")

    from services.communications_service import CommunicationsService
    rendered_subject = CommunicationsService.render_template(base_subject, sample_vars)
    rendered_html = CommunicationsService.render_template(base_html, sample_vars)

    return {
        "subject": rendered_subject,
        "html_body": rendered_html,
        "sample_variables": sample_vars,
    }


@router.post("/{campaign_id}/duplicate")
async def duplicate_campaign(
    campaign_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Duplicates an existing campaign as a new DRAFT."""
    doc = await db.campaigns.find_one({"_id": campaign_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    src = CampaignModel.from_mongo(doc)
    now = datetime.now(timezone.utc)
    new_camp = CampaignModel(
        name=f"{src.name} (Copy)",
        description=src.description,
        environment=src.environment,
        sender_email=src.sender_email,
        reply_to=src.reply_to,
        subject=src.subject,
        template_key=src.template_key,
        template_version=src.template_version,
        audience_id=src.audience_id,
        audience_source=src.audience_source,
        manual_recipients=src.manual_recipients,
        exclusions=src.exclusions,
        custom_html=src.custom_html,
        test_recipients=src.test_recipients,
        status=CampaignStatus.DRAFT,
        created_by=admin.email,
        created_at=now,
        updated_at=now,
    )
    await db.campaigns.insert_one(new_camp.to_mongo())
    return new_camp.model_dump()


@router.get("/{campaign_id}/validate")
async def validate_campaign(
    campaign_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Evaluates the pre-flight launch checklist for a campaign without launching it."""
    doc = await db.campaigns.find_one({"_id": campaign_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found.",
        )
    campaign = CampaignModel.from_mongo(doc)
    is_valid, checklist, errors = await CampaignService.validate_launch_checklist(db, campaign)
    return {
        "is_valid": is_valid,
        "checklist": checklist,
        "errors": errors,
    }


@router.post("/{campaign_id}/launch")
async def launch_campaign(
    campaign_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Validates launch checklist and launches campaign into outbox delivery."""
    service = CampaignService()
    try:
        campaign = await service.launch_campaign(db=db, campaign_id=campaign_id, actor_email=admin.email)
        return {
            "success": True,
            "campaign": campaign.model_dump(),
            "message": f"Campaign '{campaign.name}' successfully launched with {campaign.total_recipients} recipients.",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Pauses an active campaign."""
    now = datetime.now(timezone.utc)
    res = await db.campaigns.update_one(
        {"_id": campaign_id, "status": CampaignStatus.SENDING.value},
        {"$set": {"status": CampaignStatus.PAUSED.value, "updated_at": now}}
    )
    if res.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign is not in SENDING state.",
        )
    return {"success": True, "status": "paused"}


@router.post("/{campaign_id}/cancel")
async def cancel_campaign(
    campaign_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Cancels a campaign."""
    now = datetime.now(timezone.utc)
    res = await db.campaigns.update_one(
        {"_id": campaign_id, "status": {"$in": [CampaignStatus.DRAFT.value, CampaignStatus.READY.value, CampaignStatus.PAUSED.value, CampaignStatus.SCHEDULED.value]}},
        {"$set": {"status": CampaignStatus.CANCELLED.value, "updated_at": now}}
    )
    if res.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign cannot be cancelled in its current state.",
        )
    return {"success": True, "status": "cancelled"}


@router.post("/{campaign_id}/render-preview")
async def render_campaign_preview(
    campaign_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Renders the canonical preview of a campaign — exact same content that will be dispatched.
    
    Uses the same render_message() pipeline as campaign launch and test-send.
    The preview subject and body_html returned here ARE the outbox snapshot.
    There is no gap between what you see and what gets sent.
    """
    doc = await db.campaigns.find_one({"_id": campaign_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    campaign = CampaignModel.from_mongo(doc)

    from services.communications_service import CommunicationsService

    sample_vars = {
        "name": "Sarah Connor",
        "company": "Cyberdyne Systems",
        "email": "sarah@cyberdyne.io",
        "service_interest": "Cloud & AI Architecture",
        "start_time": "Aug 25, 2026, 2:00 PM UTC",
        "timezone": "UTC",
        "meeting_url": "https://navigatte.com/meet/demo",
        "unsubscribe_url": "https://navigatte.com/api/unsubscribe?email=sarah@cyberdyne.io&token=preview",
    }

    has_custom_html = bool(getattr(campaign, "custom_html", None))

    snapshot = await CommunicationsService.render_message(
        db,
        template_key=campaign.template_key if not has_custom_html and campaign.template_key != "custom" else None,
        template_version=getattr(campaign, "template_version", None),
        custom_html=getattr(campaign, "custom_html", None) if has_custom_html else None,
        subject=campaign.subject,
        variables=sample_vars,
        escape_html_in_variables=False,  # Sample vars are safe
    )

    return {
        "campaign_id": campaign_id,
        "subject": snapshot.subject,
        "html_body": snapshot.body_html,
        "template_key": snapshot.template_key,
        "template_version": snapshot.template_version,
        "sample_variables": sample_vars,
        "unresolved_variables": snapshot.unresolved_variables,
        "content_match_note": (
            "This preview is rendered by the exact same pipeline used at campaign launch. "
            "What you see here is what recipients will receive."
        ),
    }


@router.post("/{campaign_id}/send-test-campaign")
async def send_campaign_test(
    campaign_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Dispatches a test send of this campaign to its configured test_recipients ONLY.
    
    SERVER-ENFORCED SAFETY BOUNDARY:
    This endpoint NEVER uses audience contacts. Only the campaign's test_recipients
    list is used as dispatch targets. This is enforced at the server level, not just UI.
    
    Content used is exactly the campaign's current custom_html or template — the same
    content that will be used in production launch. No silent re-fetching.
    """
    doc = await db.campaigns.find_one({"_id": campaign_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    campaign = CampaignModel.from_mongo(doc)

    test_recipients = [e.lower().strip() for e in (campaign.test_recipients or []) if e.strip()]
    if not test_recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No test_recipients configured on this campaign. "
                "Add at least one test recipient before sending a test."
            ),
        )

    if not campaign.subject or not campaign.subject.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign subject is required before sending a test.",
        )

    from services.communications_service import CommunicationsService
    from integrations.resend.provider import ResendCommunicationsProvider
    from integrations.contracts.communications import EmailMessage, EmailRecipient
    from models.communications import OutboxItemModel, OutboxStatus
    from datetime import timezone

    provider = ResendCommunicationsProvider()
    if not provider.is_enabled():
        return {
            "success": False,
            "status": "provider_disabled",
            "error_message": "RESEND_API_KEY is not configured. Cannot dispatch test.",
            "test_recipients": test_recipients,
        }

    has_custom_html = bool(getattr(campaign, "custom_html", None))
    now = datetime.now(timezone.utc)
    results = []

    for recipient_email in test_recipients:
        sample_vars = {
            "name": "Test Recipient",
            "company": "Test Organization",
            "email": recipient_email,
            "service_interest": "Platform Testing",
            "unsubscribe_url": CommunicationsService.build_unsubscribe_url(recipient_email),
        }

        try:
            snapshot = await CommunicationsService.render_message(
                db,
                template_key=campaign.template_key if not has_custom_html and campaign.template_key != "custom" else None,
                template_version=getattr(campaign, "template_version", None),
                custom_html=getattr(campaign, "custom_html", None) if has_custom_html else None,
                subject=campaign.subject,
                variables=sample_vars,
            )

            idem_key = f"campaign-test:{campaign.id}:{recipient_email}:{int(now.timestamp())}"
            msg = EmailMessage(
                to=[EmailRecipient(email=recipient_email, name="Test Recipient")],
                subject=snapshot.subject,
                html_body=snapshot.body_html,
                text_body=snapshot.body_text,
                from_email=snapshot.from_email,
                idempotency_key=idem_key,
                tags={
                    "template_key": snapshot.template_key or "custom",
                    "send_type": "campaign_test",
                    "campaign_id": campaign.id,
                },
            )

            result = await provider.send_email(msg)

            # Record in outbox for audit trail
            outbox_item = OutboxItemModel(
                idempotency_key=idem_key,
                template_key=snapshot.template_key,
                recipient_email=recipient_email,
                recipient_name="Test Recipient",
                subject=snapshot.subject,
                body_html=snapshot.body_html,
                body_text=snapshot.body_text,
                from_email=snapshot.from_email,
                status=OutboxStatus.SENT if result.status == "sent" else OutboxStatus.FAILED,
                provider="resend",
                provider_message_id=result.message_id if result.status == "sent" else None,
                environment="test",
                attempt_count=1,
                sent_at=now if result.status == "sent" else None,
                error_message=result.error if result.status != "sent" else None,
                metadata={
                    "send_type": "campaign_test",
                    "campaign_id": campaign.id,
                    "sent_by": admin.email,
                    "template_version": snapshot.template_version,
                },
            )
            try:
                await db.email_outbox.insert_one(outbox_item.to_mongo())
            except Exception:
                pass

            results.append({
                "email": recipient_email,
                "status": result.status,
                "message_id": result.message_id,
                "error": result.error if result.status != "sent" else None,
            })

        except Exception as e:
            logger.error(f"Failed campaign test send to {recipient_email}: {e}")
            results.append({
                "email": recipient_email,
                "status": "error",
                "error": str(e),
            })

    sent_count = sum(1 for r in results if r["status"] == "sent")
    return {
        "success": sent_count > 0,
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "test_recipients_count": len(test_recipients),
        "sent_count": sent_count,
        "failed_count": len(test_recipients) - sent_count,
        "results": results,
        "note": "Test was dispatched to test_recipients only. Audience contacts were NOT used.",
    }
