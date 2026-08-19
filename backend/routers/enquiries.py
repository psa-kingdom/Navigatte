"""Enquiries (CRM Leads) API endpoints."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database import get_database
from core.dependencies import get_current_admin
from models.admin import AdminUser
from models.enquiry import Enquiry, EnquiryNote, EnquiryStatus
from models.project import ProjectStatus
from schemas.enquiry import (
    EnquiryCreate,
    EnquiryNoteCreate,
    EnquiryPublicResponse,
    EnquiryStatusUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["enquiries"])


# ---------------------------------------------------------------------------
# Admin Stats Aggregate
# ---------------------------------------------------------------------------

@router.get("/admin/stats", response_model=Dict[str, Any])
async def admin_get_stats(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns aggregate counts for the admin Command Center overview dashboard."""
    pipeline_statuses = [EnquiryStatus.CONTACTED.value, EnquiryStatus.QUALIFIED.value]

    enquiries_new, enquiries_pipeline, projects_total, projects_published = await _resolve_stats(
        db, pipeline_statuses
    )

    return {
        "enquiries_new": enquiries_new,
        "enquiries_pipeline": enquiries_pipeline,
        "projects_total": projects_total,
        "projects_published": projects_published,
    }


async def _resolve_stats(db: AsyncIOMotorDatabase, pipeline_statuses: list) -> tuple:
    """Helper to resolve stats counts — separated for testability."""
    enquiries_new = await db.enquiries.count_documents({"status": EnquiryStatus.NEW.value})
    enquiries_pipeline = await db.enquiries.count_documents(
        {"status": {"$in": pipeline_statuses}}
    )
    projects_total = await db.projects.count_documents({})
    projects_published = await db.projects.count_documents({"status": ProjectStatus.PUBLISHED.value})
    return enquiries_new, enquiries_pipeline, projects_total, projects_published


# ---------------------------------------------------------------------------
# Public Enquiry Ingestion
# ---------------------------------------------------------------------------

@router.post("/enquiries", response_model=EnquiryPublicResponse)
async def submit_enquiry(
    payload: EnquiryCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Public endpoint for submitting a contact enquiry or consultation request."""
    # Honeypot spam bot check: if website_hp is filled, silently discard
    if payload.website_hp:
        logger.info(f"Honeypot triggered for enquiry attempt from {payload.email}; discarding.")
        return EnquiryPublicResponse()

    data = payload.model_dump(exclude={"website_hp"})
    enquiry = Enquiry(**data)
    await db.enquiries.insert_one(enquiry.to_mongo())

    logger.info(f"New enquiry received from {payload.name} ({payload.email})")
    return EnquiryPublicResponse()


# ---------------------------------------------------------------------------
# Admin Enquiry Management
# ---------------------------------------------------------------------------

@router.get("/admin/enquiries", response_model=List[Enquiry], response_model_by_alias=False)
async def admin_list_enquiries(
    status: Optional[EnquiryStatus] = None,
    search: Optional[str] = Query(None, description="Search by name, email, or company"),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin endpoint to retrieve and filter lead enquiries."""
    query = {}
    if status:
        query["status"] = status.value

    if search:
        regex = {"$regex": search, "$options": "i"}
        query["$or"] = [
            {"name": regex},
            {"email": regex},
            {"company": regex},
        ]

    cursor = db.enquiries.find(query).sort("created_at", -1)
    docs = await cursor.to_list(1000)
    return [Enquiry.from_mongo(d) for d in docs]


@router.get("/admin/enquiries/{enquiry_id}", response_model=Enquiry, response_model_by_alias=False)
async def admin_get_enquiry(
    enquiry_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin endpoint to retrieve an enquiry with its note history."""
    if not ObjectId.is_valid(enquiry_id):
        raise HTTPException(status_code=404, detail="Enquiry not found")

    doc = await db.enquiries.find_one({"_id": ObjectId(enquiry_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    return Enquiry.from_mongo(doc)


@router.patch("/admin/enquiries/{enquiry_id}/status", response_model=Enquiry, response_model_by_alias=False)
async def admin_update_enquiry_status(
    enquiry_id: str,
    payload: EnquiryStatusUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin endpoint to advance or update the lead status in the CRM pipeline."""
    if not ObjectId.is_valid(enquiry_id):
        raise HTTPException(status_code=404, detail="Enquiry not found")

    result = await db.enquiries.update_one(
        {"_id": ObjectId(enquiry_id)},
        {
            "$set": {
                "status": payload.status.value,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    doc = await db.enquiries.find_one({"_id": ObjectId(enquiry_id)})
    return Enquiry.from_mongo(doc)


@router.post("/admin/enquiries/{enquiry_id}/notes", response_model=Enquiry, response_model_by_alias=False)
async def admin_add_enquiry_note(
    enquiry_id: str,
    payload: EnquiryNoteCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin endpoint to append a timestamped internal note to an enquiry."""
    if not ObjectId.is_valid(enquiry_id):
        raise HTTPException(status_code=404, detail="Enquiry not found")

    note = EnquiryNote(
        text=payload.text,
        created_by=admin.email,
    )

    result = await db.enquiries.update_one(
        {"_id": ObjectId(enquiry_id)},
        {
            "$push": {"notes": note.model_dump()},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    doc = await db.enquiries.find_one({"_id": ObjectId(enquiry_id)})
    return Enquiry.from_mongo(doc)
