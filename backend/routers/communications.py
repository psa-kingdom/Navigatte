"""Communications Studio & Email Control Centre Router.

Provides endpoints for email outbox inspection, template management,
delivery metrics, and live test dispatch.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr

from core.config import settings
from core.database import get_database
from core.dependencies import get_current_admin
from models.admin import AdminUser
from models.communications import EmailTemplateModel, OutboxItemModel, OutboxStatus
from services.communications_service import CommunicationsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/communications", tags=["communications"])


class SendTestEmailRequest(BaseModel):
    recipient_email: EmailStr
    recipient_name: Optional[str] = None
    template_key: str = "enquiry_acknowledgement"
    variables: Dict[str, Any] = {}


class TemplateUpdateRequest(BaseModel):
    name: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = []
    is_active: bool = True


@router.get("/overview")
async def get_communications_overview(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Returns aggregated email delivery metrics, outbox counts, and provider status."""
    # Ensure default templates are present in DB
    await CommunicationsService.ensure_default_templates(db)

    total_outbox = await db.email_outbox.count_documents({})
    sent_count = await db.email_outbox.count_documents({"status": {"$in": ["sent", "delivered", "opened", "clicked"]}})
    delivered_count = await db.email_outbox.count_documents({"status": {"$in": ["delivered", "opened", "clicked"]}})
    bounced_count = await db.email_outbox.count_documents({"status": "bounced"})
    opened_count = await db.email_outbox.count_documents({"status": {"$in": ["opened", "clicked"]}})
    failed_count = await db.email_outbox.count_documents({"status": "failed"})

    delivery_rate = round((delivered_count / sent_count * 100), 1) if sent_count > 0 else 100.0
    open_rate = round((opened_count / delivered_count * 100), 1) if delivered_count > 0 else 0.0

    has_api_key = bool(settings.RESEND_API_KEY)

    return {
        "metrics": {
            "total_outbox": total_outbox,
            "sent_count": sent_count,
            "delivered_count": delivered_count,
            "bounced_count": bounced_count,
            "opened_count": opened_count,
            "failed_count": failed_count,
            "delivery_rate_percent": delivery_rate,
            "open_rate_percent": open_rate,
        },
        "provider": {
            "name": "resend",
            "configured": has_api_key,
            "enabled": settings.RESEND_ENABLED or has_api_key,
            "sending_domain": "updates.navigatte.com",
            "from_email": settings.RESEND_FROM_EMAIL,
            "webhook_endpoint": "/api/webhooks/resend",
        },
    }


@router.get("/outbox")
async def list_outbox_items(
    status: Optional[str] = Query(None, description="Filter by status (e.g. sent, delivered, bounced, failed)"),
    search: Optional[str] = Query(None, description="Search recipient email or subject"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Lists email outbox records with search and status filtering."""
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"recipient_email": {"$regex": search, "$options": "i"}},
            {"subject": {"$regex": search, "$options": "i"}},
        ]

    total = await db.email_outbox.count_documents(query)
    cursor = db.email_outbox.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(limit)

    items = [OutboxItemModel.from_mongo(d).model_dump() for d in docs]
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "skip": skip,
    }


@router.get("/templates")
async def list_templates(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[Dict[str, Any]]:
    """Lists available email templates."""
    await CommunicationsService.ensure_default_templates(db)
    cursor = db.email_templates.find({}).sort("name", 1)
    docs = await cursor.to_list(100)
    return [EmailTemplateModel.from_mongo(d).model_dump() for d in docs]


@router.post("/templates/{key}")
async def update_template(
    key: str,
    payload: TemplateUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Updates an email template."""
    now = datetime.now(timezone.utc)
    res = await db.email_templates.update_one(
        {"key": key},
        {"$set": {
            "name": payload.name,
            "subject": payload.subject,
            "body_html": payload.body_html,
            "body_text": payload.body_text,
            "variables": payload.variables,
            "is_active": payload.is_active,
            "updated_at": now,
        }},
        upsert=True,
    )
    return {"success": True, "key": key}


@router.post("/outbox/{outbox_id}/retry")
async def retry_outbox_message(
    outbox_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Manually retries a queued or failed outbox email message."""
    service = CommunicationsService()
    try:
        item = await service.retry_outbox_item(db=db, outbox_id=outbox_id)
        return {
            "success": item.status in (OutboxStatus.SENT, OutboxStatus.DELIVERED),
            "status": item.status.value,
            "outbox_id": item.id,
            "attempt_count": item.attempt_count,
            "provider_message_id": item.provider_message_id,
            "error_message": item.error_message,
        }
    except Exception as e:
        logger.error(f"Failed to retry outbox item {outbox_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/send-test")
async def send_test_email(
    payload: SendTestEmailRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Dispatches a real test email through Resend to verify delivery."""
    service = CommunicationsService()
    item = await service.send_transactional_email(
        db=db,
        template_key=payload.template_key,
        recipient_email=payload.recipient_email,
        recipient_name=payload.recipient_name or "Test Recipient",
        variables=payload.variables or {"name": payload.recipient_name or "Admin", "service_interest": "Technical Advisory"},
    )
    return {
        "success": item.status in (OutboxStatus.SENT, OutboxStatus.DELIVERED, OutboxStatus.QUEUED),
        "status": item.status.value,
        "outbox_id": item.id,
        "provider_message_id": item.provider_message_id,
        "error_message": item.error_message,
    }
