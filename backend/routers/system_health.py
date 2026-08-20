"""Admin System Health & Operational Control Centre Router.

Provides real-time health checks, live connectivity test actions, and diagnostic inspection.
"""

import logging
import time
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.database import get_database
from core.dependencies import get_current_admin
from models.admin import AdminUser
from models.system_health import SystemHealthOverview
from services.health_service import HealthService
from integrations.cal.client import CalApiClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/system", tags=["system-health"])


@router.get("/health", response_model=SystemHealthOverview)
async def get_system_health(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> SystemHealthOverview:
    """Returns complete platform system health, integration states, and incident history."""
    return await HealthService.get_system_health(db)


@router.post("/health/cal/test", response_model=Dict[str, Any])
async def test_cal_connectivity(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Live test of outbound Cal.com API v2 connectivity."""
    client = CalApiClient()
    if not client.is_configured:
        return {
            "success": False,
            "status": "unconfigured",
            "message": "CAL_API_KEY is not configured in Railway.",
        }

    start_t = time.perf_counter()
    try:
        webhooks = await client.list_webhooks()
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return {
            "success": True,
            "status": "connected",
            "latency_ms": latency_ms,
            "message": f"Successfully connected to Cal.com API v2 ({latency_ms}ms).",
            "webhooks_count": len(webhooks) if isinstance(webhooks, list) else 0,
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        logger.error(f"Cal.com connection test failed: {e}")
        return {
            "success": False,
            "status": "error",
            "latency_ms": latency_ms,
            "message": f"Connection failed: {str(e)}",
        }


@router.post("/health/cal/test-webhook", response_model=Dict[str, Any])
async def test_cal_webhook_verification(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Tests local Cal.com webhook signature verification pipeline with the configured secret."""
    from core.config import settings
    from integrations.cal.provider import CalSchedulingProvider
    import hashlib
    import hmac

    secret = getattr(settings, "CAL_WEBHOOK_SECRET", None)
    if not secret:
        return {
            "success": False,
            "status": "unconfigured",
            "message": "CAL_WEBHOOK_SECRET is not configured in Railway.",
        }

    provider = CalSchedulingProvider()
    test_body = b'{"triggerEvent":"PING","payload":{"diagnostic":"verification"}}'
    test_sig = hmac.new(secret.encode("utf-8"), test_body, hashlib.sha256).hexdigest()

    is_valid = provider.verify_webhook_signature(
        test_body,
        {"x-cal-signature-256": test_sig},
    )

    return {
        "success": is_valid,
        "status": "verified" if is_valid else "signature_mismatch",
        "message": "HMAC-SHA256 signature verification pipeline operational." if is_valid else "Signature calculation failed.",
        "secret_length": len(secret),
    }


@router.post("/health/resend/test", response_model=Dict[str, Any])
async def test_resend_connectivity(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Live test of outbound Resend API connection."""
    from core.config import settings
    import httpx

    api_key = getattr(settings, "RESEND_API_KEY", None)
    if not api_key:
        return {
            "success": False,
            "status": "unconfigured",
            "message": "RESEND_API_KEY is not configured in Railway.",
        }

    start_t = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.resend.com/api-keys",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            if resp.status_code in (200, 403):
                return {
                    "success": True,
                    "status": "connected",
                    "latency_ms": latency_ms,
                    "message": f"Connected to Resend API ({latency_ms}ms).",
                }
            return {
                "success": False,
                "status": "auth_error",
                "latency_ms": latency_ms,
                "message": f"Resend API error: HTTP {resp.status_code}",
            }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return {
            "success": False,
            "status": "error",
            "latency_ms": latency_ms,
            "message": f"Connection error: {str(e)}",
        }


@router.post("/health/database/test", response_model=Dict[str, Any])
async def test_database_connectivity(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Live test of MongoDB Atlas cluster round-trip latency and collection counts."""
    start_t = time.perf_counter()
    try:
        await db.command("ping")
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return {
            "success": True,
            "status": "connected",
            "latency_ms": latency_ms,
            "database_name": db.name,
            "message": f"MongoDB Atlas responsive ({latency_ms}ms).",
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        logger.error(f"Database ping test failed: {e}")
        return {
            "success": False,
            "status": "error",
            "latency_ms": latency_ms,
            "message": f"Database error: {str(e)}",
        }
