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
    template_key: str
    audience_id: Optional[str] = None
    test_recipients: List[EmailStr] = []


class CampaignUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sender_email: Optional[str] = None
    reply_to: Optional[str] = None
    subject: Optional[str] = None
    template_key: Optional[str] = None
    audience_id: Optional[str] = None
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
