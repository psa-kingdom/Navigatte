"""Admin Global Search Router.

Provides unified, low-latency search across CRM enquiries, projects, and administrative entities.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.database import get_database
from models.admin import AdminUser
from routers.auth import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/search", tags=["admin-search"])


@router.get("", response_model=Dict[str, Any])
async def global_admin_search(
    q: str = Query(..., min_length=1, max_length=100, description="Search query string"),
    limit: int = Query(default=5, ge=1, le=20, description="Max results per entity category"),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """Performs scoped search across Enquiries and Projects."""
    cleaned_query = q.strip()
    if not cleaned_query:
        return {"query": "", "enquiries": [], "projects": []}

    safe_regex = {"$regex": re.escape(cleaned_query), "$options": "i"}

    # 1. Search Enquiries
    enquiries_cursor = db.enquiries.find(
        {
            "$or": [
                {"name": safe_regex},
                {"email": safe_regex},
                {"company": safe_regex},
                {"service_interest": safe_regex},
            ],
            "is_test": {"$ne": True},
        },
        {
            "_id": 1,
            "name": 1,
            "email": 1,
            "company": 1,
            "status": 1,
            "scheduling_status": 1,
            "service_interest": 1,
            "created_at": 1,
        },
    ).sort("created_at", -1).limit(limit)

    enquiry_docs = await enquiries_cursor.to_list(limit)
    enquiry_results = []
    for doc in enquiry_docs:
        enquiry_results.append({
            "id": str(doc["_id"]),
            "name": doc.get("name", "Unknown"),
            "email": doc.get("email", ""),
            "company": doc.get("company"),
            "status": doc.get("status", "new"),
            "scheduling_status": doc.get("scheduling_status", "none"),
            "service_interest": doc.get("service_interest"),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        })

    # 2. Search Projects
    projects_cursor = db.projects.find(
        {
            "$or": [
                {"title": safe_regex},
                {"client_name": safe_regex},
                {"slug": safe_regex},
                {"tags": safe_regex},
            ],
        },
        {
            "_id": 1,
            "id": 1,
            "title": 1,
            "client_name": 1,
            "slug": 1,
            "status": 1,
            "tags": 1,
            "featured": 1,
        },
    ).limit(limit)

    project_docs = await projects_cursor.to_list(limit)
    project_results = []
    for doc in project_docs:
        project_id = doc.get("id") or str(doc["_id"])
        project_results.append({
            "id": project_id,
            "title": doc.get("title", "Untitled Project"),
            "client": doc.get("client_name"),
            "slug": doc.get("slug"),
            "status": str(doc.get("status", "draft")),
            "tags": doc.get("tags", []),
            "featured": doc.get("featured", False),
        })

    return {
        "query": cleaned_query,
        "enquiries": enquiry_results,
        "projects": project_results,
    }
