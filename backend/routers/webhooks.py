"""Webhooks Ingestion Router.

Exposes unauthenticated, signature-verified ingestion endpoints for third-party providers.
"""

import json
import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.database import get_database
from integrations.cal.provider import CalSchedulingProvider
from services.scheduling_service import SchedulingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
cal_provider = CalSchedulingProvider()


@router.post("/cal")
async def receive_cal_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Public webhook ingestion endpoint for Cal.com events.

    Verifies the HMAC-SHA256 signature against the raw request body, normalizes the event,
    and updates the Navigatte CRM idempotently.
    """
    # 1. Read the EXACT raw request body bytes for signature calculation
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing request body",
        )

    # 2. Verify signature
    headers_dict = dict(request.headers)
    is_valid = cal_provider.verify_webhook_signature(raw_body, headers_dict)
    if not is_valid:
        logger.warning("Rejected unverified Cal.com webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook signature",
        )

    # 3. Parse JSON safely
    try:
        payload_dict = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Malformed JSON in Cal.com webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload",
        )

    # 4. Normalize through provider contract
    try:
        normalized_event = cal_provider.normalize_webhook(payload_dict, headers_dict)
    except Exception as e:
        logger.error(f"Failed to normalize Cal.com webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to normalize webhook event",
        )

    # 5. Process through core CRM SchedulingService
    try:
        enquiry, result = await SchedulingService.process_event(
            event=normalized_event,
            db=db,
            signature_verified=True,
        )
        return {
            "success": True,
            "status": result.get("status", "processed"),
            "enquiry_id": result.get("enquiry_id"),
            "idempotency_key": result.get("idempotency_key"),
        }
    except Exception as e:
        logger.error(f"Error processing scheduling event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal processing error during webhook ingestion",
        )
