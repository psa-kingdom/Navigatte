"""EMS Audiences and Suppression Router.

Provides endpoints for audience lists, member contacts management,
and global email suppression (unsubscribes, bounces, complaints).
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
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


class BulkImportRow(BaseModel):
    email: str
    name: Optional[str] = None
    company: Optional[str] = None
    attributes: Dict[str, Any] = {}


class BulkImportRequest(BaseModel):
    contacts: List[BulkImportRow]


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


@router.delete("/{audience_id}")
async def delete_audience(
    audience_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Deletes an audience and its associated contact records."""
    res = await db.audiences.delete_one({"_id": audience_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audience not found.")
    await db.audience_contacts.delete_many({"audience_id": audience_id})
    return {"success": True, "deleted_audience_id": audience_id}


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


@router.post("/{audience_id}/import")
async def import_audience_contacts(
    audience_id: str,
    payload: BulkImportRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Bulk imports contacts into an audience from parsed CSV or Excel data with validation."""
    import re
    aud = await db.audiences.find_one({"_id": audience_id})
    if not aud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audience not found.")

    email_regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    suppression_emails = set(await db.email_suppressions.distinct("email"))

    total_rows = len(payload.contacts)
    valid_count = 0
    invalid_count = 0
    duplicate_count = 0
    imported_count = 0
    suppressed_count = 0
    invalid_rows = []

    seen_in_batch = set()
    now = datetime.now(timezone.utc)

    for idx, row in enumerate(payload.contacts):
        raw_em = (row.email or "").strip().lower()
        if not raw_em or not email_regex.match(raw_em):
            invalid_count += 1
            invalid_rows.append({"row_index": idx + 1, "email": row.email, "error": "Invalid email syntax"})
            continue

        if raw_em in seen_in_batch:
            duplicate_count += 1
            continue

        seen_in_batch.add(raw_em)
        valid_count += 1

        is_supp = raw_em in suppression_emails
        if is_supp:
            suppressed_count += 1

        contact = AudienceContactModel(
            audience_id=audience_id,
            email=raw_em,
            name=row.name,
            company=row.company,
            attributes=row.attributes or {},
            is_suppressed=is_supp,
            created_at=now,
        )

        await db.audience_contacts.update_one(
            {"audience_id": audience_id, "email": raw_em},
            {"$set": contact.to_mongo()},
            upsert=True,
        )
        imported_count += 1

    # Update member count
    count = await db.audience_contacts.count_documents({"audience_id": audience_id})
    await db.audiences.update_one({"_id": audience_id}, {"$set": {"member_count": count, "updated_at": now}})

    # Write audit log
    audit = CommunicationsAuditLogModel(
        actor_email=admin.email,
        action="audience_contacts_imported",
        target_type="audience",
        target_id=audience_id,
        details={
            "total_rows": total_rows,
            "imported_count": imported_count,
            "suppressed_count": suppressed_count,
            "duplicate_count": duplicate_count,
        },
    )
    await db.communications_audit_logs.insert_one(audit.to_mongo())

    return {
        "total_rows": total_rows,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "duplicate_count": duplicate_count,
        "imported_count": imported_count,
        "suppressed_count": suppressed_count,
        "invalid_rows": invalid_rows[:20],
    }


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

    # Audit log
    audit = CommunicationsAuditLogModel(
        actor_email=admin.email,
        action="suppression_added",
        target_type="suppression",
        target_id=clean_email,
        details={"reason": payload.reason, "source": payload.source},
    )
    await db.communications_audit_logs.insert_one(audit.to_mongo())

    return {"success": True, "email": clean_email, "reason": payload.reason}


@router.delete("/suppression/{email}")
async def remove_suppression(
    email: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Removes an email address from global suppression."""
    clean_email = email.lower().strip()
    res = await db.email_suppressions.delete_one({"email": clean_email})
    if res.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suppression record not found.")

    await db.audience_contacts.update_many(
        {"email": clean_email},
        {"$set": {"is_suppressed": False}}
    )

    # Audit log
    audit = CommunicationsAuditLogModel(
        actor_email=admin.email,
        action="suppression_removed",
        target_type="suppression",
        target_id=clean_email,
    )
    await db.communications_audit_logs.insert_one(audit.to_mongo())

    return {"success": True, "removed_email": clean_email}


@router.post("/{audience_id}/import-file")
async def import_audience_file(
    audience_id: str,
    file: UploadFile = File(..., description="CSV or XLSX file with columns: email, name, company"),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Bulk imports contacts from an uploaded CSV or XLSX file.
    
    Expects columns: email (required), name (optional), company (optional).
    Column order and case are flexible — the endpoint will detect them automatically.
    Returns the same structured result as the JSON import endpoint.
    """
    import io
    import pandas as pd
    import re

    aud = await db.audiences.find_one({"_id": audience_id})
    if not aud:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audience not found.")

    filename = file.filename or ""
    content = await file.read()

    try:
        if filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        elif filename.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            # Attempt CSV parse as fallback
            df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse file: {e}. Ensure the file is valid CSV or XLSX.",
        )

    # Normalise column names (lowercase, strip whitespace)
    df.columns = [c.lower().strip() for c in df.columns]

    if "email" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must contain an 'email' column.",
        )

    # Build BulkImportRow list from dataframe
    contacts = []
    for _, row in df.iterrows():
        contacts.append(BulkImportRow(
            email=str(row.get("email", "") or "").strip(),
            name=str(row.get("name", "") or "").strip() or None,
            company=str(row.get("company", "") or "").strip() or None,
        ))

    # Delegate to existing import logic
    bulk_request = BulkImportRequest(contacts=contacts)

    # Inline the import logic (same as POST /{audience_id}/import)
    email_regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    suppression_emails = set(await db.email_suppressions.distinct("email"))

    total_rows = len(contacts)
    valid_count = 0
    invalid_count = 0
    duplicate_count = 0
    imported_count = 0
    suppressed_count = 0
    invalid_rows = []

    seen_in_batch: set = set()
    now = datetime.now(timezone.utc)

    for idx, row in enumerate(bulk_request.contacts):
        raw_em = (row.email or "").strip().lower()
        if not raw_em or not email_regex.match(raw_em):
            invalid_count += 1
            invalid_rows.append({"row_index": idx + 1, "email": row.email, "error": "Invalid email syntax"})
            continue

        if raw_em in seen_in_batch:
            duplicate_count += 1
            continue

        seen_in_batch.add(raw_em)
        valid_count += 1

        is_supp = raw_em in suppression_emails
        if is_supp:
            suppressed_count += 1

        from models.audience import AudienceContactModel
        contact = AudienceContactModel(
            audience_id=audience_id,
            email=raw_em,
            name=row.name,
            company=row.company,
            attributes={},
            is_suppressed=is_supp,
            created_at=now,
        )

        await db.audience_contacts.update_one(
            {"audience_id": audience_id, "email": raw_em},
            {"$set": contact.to_mongo()},
            upsert=True,
        )
        imported_count += 1

    # Update member count
    count = await db.audience_contacts.count_documents({"audience_id": audience_id})
    await db.audiences.update_one(
        {"_id": audience_id},
        {"$set": {"member_count": count, "updated_at": now}}
    )

    audit = CommunicationsAuditLogModel(
        actor_email=admin.email,
        action="audience_contacts_imported_file",
        target_type="audience",
        target_id=audience_id,
        details={
            "filename": filename,
            "total_rows": total_rows,
            "imported_count": imported_count,
            "suppressed_count": suppressed_count,
            "duplicate_count": duplicate_count,
        },
    )
    await db.communications_audit_logs.insert_one(audit.to_mongo())

    return {
        "total_rows": total_rows,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "duplicate_count": duplicate_count,
        "imported_count": imported_count,
        "suppressed_count": suppressed_count,
        "invalid_rows": invalid_rows[:20],
        "filename": filename,
    }
