"""Admin Integrations Management Router.

Protected endpoints for inspecting third-party integration health and syncing webhooks.
"""

import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import settings
from core.database import get_database
from core.dependencies import get_current_admin
from integrations.cal.provider import CalSchedulingProvider
from models.admin import AdminUser
from models.webhook_event import WebhookProcessingStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/integrations", tags=["integrations"])
cal_provider = CalSchedulingProvider()


@router.get("/status", response_model=Dict[str, Any])
async def get_integrations_status(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Returns operational status, diagnostics, and recent event stats for integrations."""
    total_events = await db.integration_webhook_events.count_documents({})
    failed_events = await db.integration_webhook_events.count_documents(
        {"processing_status": WebhookProcessingStatus.FAILED.value}
    )
    last_event_cursor = db.integration_webhook_events.find({}).sort("received_at", -1).limit(1)
    last_event_docs = await last_event_cursor.to_list(1)

    last_event_info = None
    if last_event_docs:
        last_doc = last_event_docs[0]
        last_event_info = {
            "provider": last_doc.get("provider"),
            "event_type": last_doc.get("event_type"),
            "received_at": last_doc.get("received_at"),
            "processing_status": last_doc.get("processing_status"),
        }

    return {
        "cal": {
            "name": "Cal.com",
            "enabled": settings.CAL_ENABLED,
            "has_api_key": bool(settings.CAL_API_KEY),
            "has_webhook_secret": bool(settings.CAL_WEBHOOK_SECRET),
            "subscriber_url": settings.CAL_WEBHOOK_SUBSCRIBER_URL,
            "event_type_id": settings.CAL_EVENT_TYPE_ID,
        },
        "resend": {
            "name": "Resend",
            "enabled": settings.RESEND_ENABLED,
            "has_api_key": bool(settings.RESEND_API_KEY),
            "has_webhook_secret": bool(settings.RESEND_WEBHOOK_SECRET),
            "from_email": settings.RESEND_FROM_EMAIL,
            "sending_domain": "updates.navigatte.com",
        },
        "stats": {
            "total_events_received": total_events,
            "failed_events": failed_events,
            "last_event": last_event_info,
        },
    }


@router.post("/cal/sync", response_model=Dict[str, Any])
async def sync_cal_webhook(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Syncs/registers the webhook with the configured Cal.com account."""
    subscriber_url = settings.CAL_WEBHOOK_SUBSCRIBER_URL or "https://navigatte.com/api/webhooks/cal"
    try:
        result = await cal_provider.sync_webhook(subscriber_url=subscriber_url)
        return {
            "success": True,
            "result": result,
        }
    except Exception as e:
        logger.error(f"Error syncing Cal.com webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync Cal.com webhook: {str(e)}",
        )
