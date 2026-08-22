"""System status and root endpoints."""

from datetime import datetime, timezone
from typing import List
import uuid
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, ConfigDict, Field
from core.database import get_database

router = APIRouter(tags=["status"])


class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


@router.get("/")
async def root():
    return {"message": "Hello World", "app": "Navigatte API"}


@router.post("/status", response_model=StatusCheck)
async def create_status_check(
    input: StatusCheckCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj


@router.get("/status", response_model=List[StatusCheck])
async def get_status_checks(db: AsyncIOMotorDatabase = Depends(get_database)):
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check.get("timestamp"), str):
            check["timestamp"] = datetime.fromisoformat(check["timestamp"])
    return status_checks


@router.get("/system/version")
async def get_system_version():
    """Returns API build version, communications engine version, and environment metadata for deployment parity."""
    from core.config import settings
    return {
        "application": "Navigatte API",
        "version": "1.2.0",
        "communications_version": "2.0.0",
        "environment": getattr(settings, "COMMUNICATIONS_ENVIRONMENT", "test"),
        "delivery_worker": "active",
        "canonical_render": "enabled",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
