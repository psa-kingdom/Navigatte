"""Communications Studio & Email Control Centre Router.

Provides endpoints for email outbox inspection, template management,
delivery metrics, and live test dispatch via the canonical render pipeline.
"""

from datetime import datetime, timezone
import io
import logging
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase
import pandas as pd
from pydantic import BaseModel, EmailStr

from core.config import settings
from core.database import get_database
from core.dependencies import get_current_admin
from models.admin import AdminUser
from models.communications import EmailTemplateModel, OutboxItemModel, OutboxStatus
from services.communications_service import CommunicationsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/communications", tags=["communications"])


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class SendTestEmailRequest(BaseModel):
    """Request body for /send-test.
    
    Accepts single recipient_email or multiple recipient_emails list.
    Accepts either a template_key (with optional version) or custom_html.
    The backend will use the canonical render_message() pipeline with exactly
    the content provided — no silent template re-fetching.
    """
    recipient_email: Optional[EmailStr] = None
    recipient_emails: Optional[List[EmailStr]] = None
    recipient_name: Optional[str] = None

    # Content source: custom_html takes priority over template_key
    template_key: Optional[str] = None
    template_version: Optional[int] = None  # None = active/latest version
    custom_html: Optional[str] = None       # Raw HTML body to send AS-IS

    # Subject: required for meaningful test; overrides template subject
    subject: Optional[str] = None

    # Template variables for substitution
    variables: Dict[str, Any] = {}


class TemplateUpdateRequest(BaseModel):
    name: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = []
    is_active: bool = True


class TemplateCreateRequest(BaseModel):
    key: str
    name: str
    category: str = "transactional"  # 'transactional' | 'campaign'
    subject: str
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = []
    provider: str = "navigatte"
    # Note: provider_template_id (Resend-hosted templates) is reserved for future use.
    # It is not exposed in the composer as Resend template ID dispatch is not yet supported.


# ============================================================================
# OVERVIEW & DIAGNOSTICS
# ============================================================================

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
        "worker": {
            "status": "running",  # Worker is always running via lifespan background task
            "note": "Delivery worker runs as a persistent asyncio background task in FastAPI lifespan.",
        },
        "system": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.post("/parse-import-file")
async def parse_import_file(
    file: UploadFile = File(...),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Parses an uploaded CSV, XLSX, XLS, or TXT file and intelligently extracts email addresses across all columns."""
    filename = file.filename or "uploaded_file"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    email_regex = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    extracted_emails: List[str] = []
    total_rows = 0
    invalid_rows = 0

    if ext in ("xlsx", "xls"):
        try:
            excel_data = pd.read_excel(io.BytesIO(contents), sheet_name=None, header=None)
            for sheet_name, df in excel_data.items():
                total_rows += len(df)
                for _, row in df.iterrows():
                    row_had_email = False
                    for cell in row:
                        if cell is not None and not pd.isna(cell):
                            cell_str = str(cell).strip()
                            found = email_regex.findall(cell_str)
                            if found:
                                row_had_email = True
                                for em in found:
                                    extracted_emails.append(em.lower().strip())
                    if not row_had_email and not row.isna().all():
                        invalid_rows += 1
        except Exception as e:
            logger.error(f"Failed to parse Excel file {filename}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to parse Excel file: {str(e)}")
    elif ext in ("csv",):
        try:
            df = pd.read_csv(io.BytesIO(contents))
            total_rows = len(df)
            for _, row in df.iterrows():
                row_had_email = False
                for cell in row:
                    if cell is not None and not pd.isna(cell):
                        cell_str = str(cell).strip()
                        found = email_regex.findall(cell_str)
                        if found:
                            row_had_email = True
                            for em in found:
                                extracted_emails.append(em.lower().strip())
                if not row_had_email:
                    invalid_rows += 1
        except Exception:
            # Fallback to plain line scanning
            try:
                text = contents.decode("utf-8")
            except UnicodeDecodeError:
                text = contents.decode("latin-1", errors="ignore")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            total_rows = len(lines)
            for line in lines:
                found = email_regex.findall(line)
                if found:
                    for em in found:
                        extracted_emails.append(em.lower().strip())
                else:
                    invalid_rows += 1
    else:
        # Plain text
        try:
            text = contents.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = contents.decode("latin-1")
            except Exception:
                text = contents.decode("utf-8", errors="ignore")

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        total_rows = len(lines)
        for line in lines:
            found = email_regex.findall(line)
            if found:
                for em in found:
                    extracted_emails.append(em.lower().strip())
            else:
                invalid_rows += 1

    # Deduplicate within this import batch
    unique_emails: List[str] = []
    seen = set()
    duplicate_count = 0
    for em in extracted_emails:
        if em in seen:
            duplicate_count += 1
        else:
            seen.add(em)
            unique_emails.append(em)

    # Check suppression list
    suppression_emails = set(await db.email_suppressions.distinct("email"))
    suppressed = [e for e in unique_emails if e in suppression_emails]
    valid_unsuppressed = [e for e in unique_emails if e not in suppression_emails]

    return {
        "filename": filename,
        "total_rows": total_rows,
        "valid_emails": valid_unsuppressed,
        "valid_count": len(valid_unsuppressed),
        "duplicate_count": duplicate_count,
        "invalid_count": invalid_rows,
        "suppressed_count": len(suppressed),
        "suppressed_emails": suppressed,
    }


# ============================================================================
# OUTBOX
# ============================================================================

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


@router.get("/resend/emails/{message_id}")
async def get_resend_email_status(
    message_id: str,
    admin: AdminUser = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Queries Resend API directly for the live delivery event status of a specific message ID."""
    from integrations.resend.client import ResendApiClient
    client = ResendApiClient()
    if not client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resend API key is not configured.",
        )
    try:
        data = await client.get_email(message_id)
        return {"success": True, "email": data}
    except Exception as e:
        logger.error(f"Failed to query Resend for email {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================================
# TEST EMAIL DISPATCH (THE CANONICAL SEND-TEST ENDPOINT)
# ============================================================================

@router.post("/send-test")
async def send_test_email(
    payload: SendTestEmailRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Dispatches a real test email through Resend using the canonical render pipeline.
    
    Accepts single recipient_email or multiple recipient_emails.
    Accepts either custom_html or template_key.
    The content sent is EXACTLY what was provided — no silent template re-fetching.
    """
    # 1. Resolve recipients
    target_emails = []
    if payload.recipient_emails:
        target_emails = [e.lower().strip() for e in payload.recipient_emails if e and e.strip()]
    elif payload.recipient_email:
        target_emails = [payload.recipient_email.lower().strip()]

    if not target_emails:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one test recipient email is required (recipient_email or recipient_emails).",
        )

    # 2. Determine content source
    has_custom_html = bool(payload.custom_html and payload.custom_html.strip())
    has_template = bool(payload.template_key and payload.template_key not in ("custom", ""))

    if not has_custom_html and not has_template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either custom_html or a valid template_key must be provided.",
        )

    if not payload.subject or not payload.subject.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject line is required for test dispatch.",
        )

    # 3. Canonical render pipeline (one single render for consistency)
    snapshot = await CommunicationsService.render_message(
        db,
        template_key=payload.template_key if has_template and not has_custom_html else None,
        template_version=payload.template_version,
        custom_html=payload.custom_html if has_custom_html else None,
        subject=payload.subject,
        variables=payload.variables or {},
    )

    from integrations.resend.provider import ResendCommunicationsProvider
    from integrations.contracts.communications import EmailMessage, EmailRecipient
    from models.communications import OutboxItemModel, OutboxStatus
    from datetime import timezone

    provider = ResendCommunicationsProvider()
    from_email = snapshot.from_email
    environment = getattr(settings, "COMMUNICATIONS_ENVIRONMENT", "test")
    now = datetime.now(timezone.utc)

    if not provider.is_enabled():
        return {
            "success": False,
            "status": "provider_disabled",
            "error_message": (
                "Email delivery is currently unconfigured: RESEND_API_KEY is missing on this environment. "
                "Set RESEND_API_KEY to enable live email delivery."
            ),
            "preview": {
                "subject": snapshot.subject,
                "body_html": snapshot.body_html,
                "template_key": snapshot.template_key,
                "template_version": snapshot.template_version,
                "unresolved_variables": snapshot.unresolved_variables,
            },
            "sent_count": 0,
            "failed_count": len(target_emails),
            "total_recipients": len(target_emails),
            "results": [{"email": e, "status": "provider_disabled", "error": "RESEND_API_KEY is not configured"} for e in target_emails],
            "environment": environment,
        }

    results = []
    first_outbox_id = None
    first_msg_id = None

    for email_addr in target_emails:
        idem_key = f"test:{email_addr}:{admin.email}:{int(now.timestamp())}"
        msg = EmailMessage(
            to=[EmailRecipient(email=email_addr, name=payload.recipient_name or "Test Recipient")],
            subject=snapshot.subject,
            html_body=snapshot.body_html,
            text_body=snapshot.body_text,
            from_email=from_email,
            idempotency_key=idem_key,
            tags={"template_key": snapshot.template_key or "custom", "send_type": "test"},
        )

        res = await provider.send_email(msg)

        outbox_item = OutboxItemModel(
            idempotency_key=idem_key,
            template_key=snapshot.template_key,
            recipient_email=email_addr,
            recipient_name=payload.recipient_name or "Test Recipient",
            subject=snapshot.subject,
            body_html=snapshot.body_html,
            body_text=snapshot.body_text,
            from_email=from_email,
            status=OutboxStatus.SENT if res.status == "sent" else OutboxStatus.FAILED,
            provider="resend",
            provider_message_id=res.message_id if res.status == "sent" else None,
            environment=environment,
            attempt_count=1,
            sent_at=now if res.status == "sent" else None,
            error_message=res.error if res.status != "sent" else None,
            metadata={
                "send_type": "manual_test",
                "sent_by": admin.email,
                "template_version": snapshot.template_version,
            },
            tags={"template_key": snapshot.template_key or "custom", "send_type": "test"},
        )
        try:
            await db.email_outbox.insert_one(outbox_item.to_mongo())
        except Exception:
            pass

        if not first_outbox_id:
            first_outbox_id = outbox_item.id
            first_msg_id = res.message_id

        results.append({
            "email": email_addr,
            "status": res.status,
            "message_id": res.message_id,
            "error": res.error if res.status != "sent" else None,
        })

    sent_count = sum(1 for r in results if r["status"] == "sent")
    is_success = sent_count > 0

    return {
        "success": is_success,
        "status": "sent" if is_success else "failed",
        "sent_count": sent_count,
        "failed_count": len(target_emails) - sent_count,
        "total_recipients": len(target_emails),
        "outbox_id": first_outbox_id,
        "provider_message_id": first_msg_id,
        "results": results,
        "environment": environment,
        "preview": {
            "subject": snapshot.subject,
            "body_html": snapshot.body_html,
            "template_key": snapshot.template_key,
            "template_version": snapshot.template_version,
            "unresolved_variables": snapshot.unresolved_variables,
        },
    }


# ============================================================================
# TEMPLATES
# ============================================================================

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


@router.get("/templates/{key}/preview")
async def preview_template(
    key: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Renders a live preview of the template with realistic placeholder data."""
    tpl_doc = await db.email_templates.find_one({"key": key})
    if not tpl_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    tpl = EmailTemplateModel.from_mongo(tpl_doc)

    sample_vars = _get_sample_variables(tpl_doc.get("recipient_email", "preview@example.com"))

    snapshot = await CommunicationsService.render_message(
        db,
        template_key=key,
        subject=tpl.subject,
        variables=sample_vars,
        escape_html_in_variables=False,  # Sample vars are safe
    )

    return {
        "key": tpl.key,
        "name": tpl.name,
        "version": tpl.version,
        "subject": snapshot.subject,
        "html_body": snapshot.body_html,
        "sample_variables": sample_vars,
        "unresolved_variables": snapshot.unresolved_variables,
    }


@router.get("/templates/{key}/versions/{version_number}/preview")
async def preview_template_version(
    key: str,
    version_number: int,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Renders a preview of a specific historical template version.
    
    This allows previewing and test-sending historical versions without
    needing to restore them to the active template first.
    """
    v_doc = await db.email_template_versions.find_one({"template_key": key, "version": version_number})
    if not v_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template version {key}@v{version_number} not found.",
        )

    sample_vars = _get_sample_variables("preview@example.com")

    snapshot = await CommunicationsService.render_message(
        db,
        template_key=key,
        template_version=version_number,
        subject=v_doc.get("subject"),
        variables=sample_vars,
        escape_html_in_variables=False,
    )

    return {
        "key": key,
        "version": version_number,
        "name": v_doc.get("name"),
        "subject": snapshot.subject,
        "html_body": snapshot.body_html,
        "sample_variables": sample_vars,
        "unresolved_variables": snapshot.unresolved_variables,
        "created_at": v_doc.get("created_at"),
        "change_summary": v_doc.get("change_summary"),
    }


@router.post("/templates/{key}/duplicate")
async def duplicate_template(
    key: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Duplicates an existing template as a new custom template."""
    src_doc = await db.email_templates.find_one({"key": key})
    if not src_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source template not found.")

    src = EmailTemplateModel.from_mongo(src_doc)
    new_key = f"{src.key}_copy"
    suffix = 1
    while await db.email_templates.find_one({"key": new_key}):
        suffix += 1
        new_key = f"{src.key}_copy_{suffix}"

    now = datetime.now(timezone.utc)
    new_tpl = EmailTemplateModel(
        key=new_key,
        name=f"{src.name} (Copy)",
        category=src.category,
        subject=src.subject,
        body_html=src.body_html,
        body_text=src.body_text,
        variables=src.variables,
        version=1,
        is_active=True,
        is_system=False,
        provider=src.provider,
        created_by=admin.email,
        created_at=now,
        updated_at=now,
    )
    await db.email_templates.insert_one(new_tpl.to_mongo())

    from models.template_version import EmailTemplateVersionModel
    v_snapshot = EmailTemplateVersionModel(
        template_id=new_tpl.id,
        template_key=new_tpl.key,
        version=1,
        name=new_tpl.name,
        subject=new_tpl.subject,
        body_html=new_tpl.body_html,
        body_text=new_tpl.body_text,
        variables=new_tpl.variables,
        created_by=admin.email,
        change_summary="Duplicated from " + key,
    )
    await db.email_template_versions.insert_one(v_snapshot.to_mongo())

    return new_tpl.model_dump()


@router.post("/templates/{key}/restore/{version_number}")
async def restore_template_version(
    key: str,
    version_number: int,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Restores a template to content from a previous version snapshot and increments the version."""
    v_doc = await db.email_template_versions.find_one({"template_key": key, "version": version_number})
    if not v_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version snapshot not found.")

    tpl_doc = await db.email_templates.find_one({"key": key})
    if not tpl_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    current_version = tpl_doc.get("version", 1)
    new_version = current_version + 1
    now = datetime.now(timezone.utc)

    await db.email_templates.update_one(
        {"key": key},
        {"$set": {
            "name": v_doc.get("name"),
            "subject": v_doc.get("subject"),
            "body_html": v_doc.get("body_html"),
            "body_text": v_doc.get("body_text"),
            "variables": v_doc.get("variables", []),
            "version": new_version,
            "updated_by": admin.email,
            "updated_at": now,
        }}
    )

    from models.template_version import EmailTemplateVersionModel
    v_snapshot = EmailTemplateVersionModel(
        template_id=str(tpl_doc.get("_id")),
        template_key=key,
        version=new_version,
        name=v_doc.get("name"),
        subject=v_doc.get("subject"),
        body_html=v_doc.get("body_html"),
        body_text=v_doc.get("body_text"),
        variables=v_doc.get("variables", []),
        created_by=admin.email,
        change_summary=f"Restored from version {version_number}",
    )
    await db.email_template_versions.insert_one(v_snapshot.to_mongo())

    return {"success": True, "key": key, "version": new_version, "restored_from": version_number}


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


# ============================================================================
# ANALYTICS & AUDIT
# ============================================================================

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


# ============================================================================
# HELPERS
# ============================================================================

def _get_sample_variables(recipient_email: str = "sarah@cyberdyne.io") -> Dict[str, Any]:
    """Returns realistic sample variable values for preview rendering."""
    return {
        "name": "Sarah Connor",
        "company": "Cyberdyne Systems",
        "email": recipient_email,
        "service_interest": "Cloud & AI Architecture",
        "start_time": "Aug 25, 2026, 2:00 PM UTC",
        "timezone": "UTC",
        "meeting_url": "https://navigatte.com/meet/demo-session",
        "unsubscribe_url": f"https://navigatte.com/api/unsubscribe?email={recipient_email}&token=preview",
    }
