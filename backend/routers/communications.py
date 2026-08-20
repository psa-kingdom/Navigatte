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


class TemplateCreateRequest(BaseModel):
    key: str
    name: str
    category: str = "transactional"  # 'transactional' | 'campaign'
    subject: str
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = []
    provider: str = "navigatte"
    provider_template_id: Optional[str] = None


@router.get("/templates")
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[Dict[str, Any]]:
    """Lists available email templates."""
    await CommunicationsService.ensure_default_templates(db)
    query: Dict[str, Any] = {}
    if category:
        query["category"] = category
    cursor = db.email_templates.find(query).sort("name", 1)
    docs = await cursor.to_list(100)
    return [EmailTemplateModel.from_mongo(d).model_dump() for d in docs]


@router.post("/templates")
async def create_template(
    payload: TemplateCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Creates a new custom email template with initial versioning."""
    clean_key = payload.key.strip().lower().replace(" ", "_")
    existing = await db.email_templates.find_one({"key": clean_key})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template with key '{clean_key}' already exists.",
        )

    now = datetime.now(timezone.utc)
    tpl = EmailTemplateModel(
        key=clean_key,
        name=payload.name,
        category=payload.category,
        subject=payload.subject,
        body_html=payload.body_html,
        body_text=payload.body_text,
        variables=payload.variables,
        version=1,
        is_active=True,
        is_system=False,
        provider=payload.provider,
        provider_template_id=payload.provider_template_id,
        created_by=admin.email,
        created_at=now,
        updated_at=now,
    )
    await db.email_templates.insert_one(tpl.to_mongo())

    # Create initial version snapshot
    from models.template_version import EmailTemplateVersionModel
    v_snapshot = EmailTemplateVersionModel(
        template_id=tpl.id,
        template_key=tpl.key,
        version=1,
        name=tpl.name,
        subject=tpl.subject,
        body_html=tpl.body_html,
        body_text=tpl.body_text,
        variables=tpl.variables,
        created_by=admin.email,
        change_summary="Initial template creation",
    )
    await db.email_template_versions.insert_one(v_snapshot.to_mongo())

    return tpl.model_dump()


@router.post("/templates/{key}")
async def update_template(
    key: str,
    payload: TemplateUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Updates an email template, increments version, and creates an immutable version snapshot."""
    now = datetime.now(timezone.utc)
    existing_doc = await db.email_templates.find_one({"key": key})
    if not existing_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    current_version = existing_doc.get("version", 1)
    new_version = current_version + 1

    await db.email_templates.update_one(
        {"key": key},
        {"$set": {
            "name": payload.name,
            "subject": payload.subject,
            "body_html": payload.body_html,
            "body_text": payload.body_text,
            "variables": payload.variables,
            "is_active": payload.is_active,
            "version": new_version,
            "updated_by": admin.email,
            "updated_at": now,
        }}
    )

    # Save immutable version snapshot
    from models.template_version import EmailTemplateVersionModel
    v_snapshot = EmailTemplateVersionModel(
        template_id=str(existing_doc.get("_id")),
        template_key=key,
        version=new_version,
        name=payload.name,
        subject=payload.subject,
        body_html=payload.body_html,
        body_text=payload.body_text,
        variables=payload.variables,
        created_by=admin.email,
        change_summary=f"Updated to version {new_version}",
    )
    await db.email_template_versions.insert_one(v_snapshot.to_mongo())

    return {"success": True, "key": key, "version": new_version}


@router.get("/templates/{key}/versions")
async def list_template_versions(
    key: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[Dict[str, Any]]:
    """Lists historical version snapshots of a template."""
    from models.template_version import EmailTemplateVersionModel
    cursor = db.email_template_versions.find({"template_key": key}).sort("version", -1)
    docs = await cursor.to_list(50)
    return [EmailTemplateVersionModel.from_mongo(d).model_dump() for d in docs]


@router.delete("/templates/{key}")
async def delete_template(
    key: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Deletes/archives a custom template. System templates cannot be deleted."""
    tpl_doc = await db.email_templates.find_one({"key": key})
    if not tpl_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    if tpl_doc.get("is_system", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Protected system templates cannot be deleted.",
        )

    await db.email_templates.delete_one({"key": key})
    return {"success": True, "key": key, "deleted": True}


@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Lists EMS administrative and lifecycle audit log entries."""
    from models.audit import CommunicationsAuditLogModel
    total = await db.communications_audit_logs.count_documents({})
    cursor = db.communications_audit_logs.find({}).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(limit)
    items = [CommunicationsAuditLogModel.from_mongo(d).model_dump() for d in docs]
    return {"items": items, "total": total, "limit": limit, "skip": skip}


@router.get("/analytics")
async def get_communications_analytics(
    environment: Optional[str] = Query(None),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Returns derived delivery, bounce, open, click, and failure metrics with zero-guards."""
    query: Dict[str, Any] = {}
    if environment:
        query["environment"] = environment

    total_dispatches = await db.email_outbox.count_documents(query)
    sent_count = await db.email_outbox.count_documents({**query, "status": {"$in": ["sent", "delivered", "opened", "clicked"]}})
    delivered_count = await db.email_outbox.count_documents({**query, "status": {"$in": ["delivered", "opened", "clicked"]}})
    opened_count = await db.email_outbox.count_documents({**query, "status": {"$in": ["opened", "clicked"]}})
    clicked_count = await db.email_outbox.count_documents({**query, "status": "clicked"})
    bounced_count = await db.email_outbox.count_documents({**query, "status": "bounced"})
    complained_count = await db.email_outbox.count_documents({**query, "status": "complained"})
    failed_count = await db.email_outbox.count_documents({**query, "status": "failed"})

    delivery_rate = round((delivered_count / sent_count * 100), 2) if sent_count > 0 else 0.0
    open_rate = round((opened_count / delivered_count * 100), 2) if delivered_count > 0 else 0.0
    click_rate = round((clicked_count / opened_count * 100), 2) if opened_count > 0 else 0.0
    bounce_rate = round((bounced_count / sent_count * 100), 2) if sent_count > 0 else 0.0

    return {
        "totals": {
            "total_outbox": total_dispatches,
            "sent": sent_count,
            "delivered": delivered_count,
            "opened": opened_count,
            "clicked": clicked_count,
            "bounced": bounced_count,
            "complained": complained_count,
            "failed": failed_count,
        },
        "rates": {
            "delivery_rate_percent": delivery_rate,
            "open_rate_percent": open_rate,
            "click_rate_percent": click_rate,
            "bounce_rate_percent": bounce_rate,
        },
    }



@router.get("/outbox/{outbox_id}")
async def get_outbox_item(
    outbox_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Retrieves a single outbox message by ID with full delivery telemetry."""
    doc = await db.email_outbox.find_one({"_id": outbox_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outbox message '{outbox_id}' not found.",
        )
    return OutboxItemModel.from_mongo(doc).model_dump()


@router.get("/diagnostics")
async def get_communications_diagnostics(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Returns runtime EMS health, provider readiness, and environment boundaries."""
    has_api_key = bool(settings.RESEND_API_KEY)
    is_enabled = settings.RESEND_ENABLED
    env = getattr(settings, "COMMUNICATIONS_ENVIRONMENT", "test")
    allowed_recipients = settings.ALLOWED_TEST_RECIPIENTS

    return {
        "provider": {
            "name": "resend",
            "has_api_key": has_api_key,
            "is_enabled": is_enabled,
            "sending_domain": "updates.navigatte.com",
            "from_email": settings.RESEND_FROM_EMAIL,
            "has_webhook_secret": bool(settings.RESEND_WEBHOOK_SECRET),
        },
        "environment": {
            "current": env,
            "is_production": env == "production",
            "campaign_test_mode": env != "production",
            "allowed_test_recipients_count": len(allowed_recipients),
            "allowed_test_recipients": allowed_recipients,
        },
        "system": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


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
        is_success = item.status in (OutboxStatus.SENT, OutboxStatus.DELIVERED)
        return {
            "success": is_success,
            "status": item.status.value,
            "outbox_id": item.id,
            "attempt_count": item.attempt_count,
            "provider_message_id": item.provider_message_id,
            "error_message": item.error_message,
            "is_retryable": item.is_retryable,
            "environment": item.environment,
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
    """Dispatches a real test email through Resend to verify delivery. Never claims success if unconfigured."""
    service = CommunicationsService()
    item = await service.send_transactional_email(
        db=db,
        template_key=payload.template_key,
        recipient_email=payload.recipient_email,
        recipient_name=payload.recipient_name or "Test Recipient",
        variables=payload.variables or {"name": payload.recipient_name or "Admin", "service_interest": "Technical Advisory"},
    )
    is_success = item.status in (OutboxStatus.SENT, OutboxStatus.DELIVERED)
    return {
        "success": is_success,
        "status": item.status.value,
        "outbox_id": item.id,
        "provider_message_id": item.provider_message_id,
        "error_message": item.error_message,
        "is_retryable": item.is_retryable,
        "attempt_count": item.attempt_count,
        "environment": item.environment,
    }

