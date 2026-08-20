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
