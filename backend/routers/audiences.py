"""EMS Audiences and Suppression Router.

Provides endpoints for audience lists, member contacts management,
and global email suppression (unsubscribes, bounces, complaints).
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
from models.audience import AudienceContactModel, AudienceModel, SuppressionRecordModel
from models.audit import CommunicationsAuditLogModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/communications/audiences", tags=["audiences"])


class AudienceCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    tags: List[str] = []


class AddContactRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    company: Optional[str] = None
    attributes: Dict[str, Any] = {}


class SuppressionCreateRequest(BaseModel):
    email: EmailStr
    reason: str = "manual"  # 'unsubscribed' | 'hard_bounce' | 'complaint' | 'manual'
    source: Optional[str] = "admin_manual"


@router.get("")
async def list_audiences(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Lists audience groups with contact counts."""
    cursor = db.audiences.find({}).sort("created_at", -1)
    docs = await cursor.to_list(100)
    items = [AudienceModel.from_mongo(d).model_dump() for d in docs]
    return {"items": items, "total": len(items)}


@router.post("")
async def create_audience(
    payload: AudienceCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Creates a new audience group."""
    now = datetime.now(timezone.utc)
    audience = AudienceModel(
        name=payload.name,
        description=payload.description,
        tags=payload.tags,
        member_count=0,
        created_by=admin.email,
        created_at=now,
        updated_at=now,
    )
    await db.audiences.insert_one(audience.to_mongo())
    return audience.model_dump()


@router.get("/{audience_id}/contacts")
async def list_audience_contacts(
    audience_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Lists contacts within a given audience."""
    total = await db.audience_contacts.count_documents({"audience_id": audience_id})
    cursor = db.audience_contacts.find({"audience_id": audience_id}).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(limit)
    items = [AudienceContactModel.from_mongo(d).model_dump() for d in docs]
    return {"items": items, "total": total, "limit": limit, "skip": skip}


@router.post("/{audience_id}/contacts")
async def add_audience_contact(
    audience_id: str,
    payload: AddContactRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Adds or updates a contact within an audience."""
    aud = await db.audiences.find_one({"_id": audience_id})
    if not aud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audience not found.")

    clean_email = payload.email.lower().strip()
    now = datetime.now(timezone.utc)

    # Check suppression
    is_suppressed = bool(await db.email_suppressions.find_one({"email": clean_email}))

    contact = AudienceContactModel(
        audience_id=audience_id,
        email=clean_email,
        name=payload.name,
        company=payload.company,
        attributes=payload.attributes,
        is_suppressed=is_suppressed,
        created_at=now,
    )

    await db.audience_contacts.update_one(
        {"audience_id": audience_id, "email": clean_email},
        {"$set": contact.to_mongo()},
        upsert=True,
    )

    # Update member count
    count = await db.audience_contacts.count_documents({"audience_id": audience_id})
    await db.audiences.update_one({"_id": audience_id}, {"$set": {"member_count": count, "updated_at": now}})

    return contact.model_dump()


# Suppression Endpoints
@router.get("/suppression")
async def list_suppressions(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Lists globally suppressed email addresses."""
    total = await db.email_suppressions.count_documents({})
    cursor = db.email_suppressions.find({}).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(limit)
    items = [SuppressionRecordModel.from_mongo(d).model_dump() for d in docs]
    return {"items": items, "total": total, "limit": limit, "skip": skip}


@router.post("/suppression")
async def add_suppression(
    payload: SuppressionCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Adds an email address to global suppression."""
    clean_email = payload.email.lower().strip()
    now = datetime.now(timezone.utc)

    record = SuppressionRecordModel(
        email=clean_email,
        reason=payload.reason,
        source=payload.source,
        created_at=now,
        created_by=admin.email,
    )

    await db.email_suppressions.update_one(
        {"email": clean_email},
        {"$set": record.to_mongo()},
        upsert=True,
    )

    # Mark contacts with this email as suppressed
    await db.audience_contacts.update_many(
        {"email": clean_email},
        {"$set": {"is_suppressed": True}}
    )

    return {"success": True, "email": clean_email, "reason": payload.reason}
