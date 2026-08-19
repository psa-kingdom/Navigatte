"""Projects and Case Studies API endpoints."""

from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database import get_database
from core.dependencies import get_current_admin
from models.admin import AdminUser
from models.project import Project, ProjectStatus, PREDEFINED_TAGS, generate_slug
from schemas.project import ProjectCreate, ProjectUpdate

router = APIRouter(tags=["projects"])


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@router.get("/tags", response_model=List[str])
async def list_tags(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Returns list of distinct tags across projects combined with predefined suggestions."""
    distinct_tags = await db.projects.distinct("tags")
    merged = sorted(set(PREDEFINED_TAGS) | set(distinct_tags))
    return merged


# ---------------------------------------------------------------------------
# Public Projects
# ---------------------------------------------------------------------------

@router.get("/projects", response_model=List[Project], response_model_by_alias=False)
async def list_projects(
    featured: Optional[bool] = None,
    tag: Optional[str] = None,
    industry: Optional[str] = None,
    status: Optional[ProjectStatus] = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Lists projects. By default for public queries, includes published projects."""
    query = {}
    if status is not None:
        query["status"] = status.value
    else:
        # Default to published projects or projects with no status specified (backward compatibility)
        query["$or"] = [
            {"status": ProjectStatus.PUBLISHED.value},
            {"status": {"$exists": False}},
        ]

    if featured is not None:
        query["featured"] = featured
    if tag:
        query["tags"] = tag
    if industry:
        query["industry_slug"] = industry

    cursor = db.projects.find(query).sort([("order", 1), ("created_at", -1)])
    docs = await cursor.to_list(1000)
    return [Project.from_mongo(d) for d in docs]


@router.get("/projects/{id_or_slug}", response_model=Project, response_model_by_alias=False)
async def get_project(
    id_or_slug: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Retrieves a single project by either ObjectId string or URL slug."""
    doc = None
    if ObjectId.is_valid(id_or_slug):
        doc = await db.projects.find_one({"_id": ObjectId(id_or_slug)})

    if not doc:
        doc = await db.projects.find_one({"slug": id_or_slug})

    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")

    return Project.from_mongo(doc)


# ---------------------------------------------------------------------------
# Admin Projects CRUD
# ---------------------------------------------------------------------------

@router.get("/admin/projects", response_model=List[Project], response_model_by_alias=False)
async def admin_list_projects(
    status: Optional[ProjectStatus] = None,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin endpoint to retrieve all projects across all lifecycle statuses."""
    query = {}
    if status is not None:
        query["status"] = status.value

    cursor = db.projects.find(query).sort([("order", 1), ("created_at", -1)])
    docs = await cursor.to_list(1000)
    return [Project.from_mongo(d) for d in docs]


@router.post("/projects", response_model=Project, response_model_by_alias=False)
@router.post("/admin/projects", response_model=Project, response_model_by_alias=False)
async def create_project(
    payload: ProjectCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Creates a new project record."""
    data = payload.model_dump()
    if not data.get("slug"):
        data["slug"] = generate_slug(payload.title)

    project = Project(**data)
    await db.projects.insert_one(project.to_mongo())
    return project


@router.put("/projects/{project_id}", response_model=Project, response_model_by_alias=False)
@router.put("/admin/projects/{project_id}", response_model=Project, response_model_by_alias=False)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Updates an existing project record."""
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    updates["updated_at"] = datetime.now(timezone.utc)

    if updates:
        try:
            result = await db.projects.update_one(
                {"_id": ObjectId(project_id)}, {"$set": updates}
            )
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Project not found")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="Project not found")

    doc = await db.projects.find_one({"_id": ObjectId(project_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return Project.from_mongo(doc)


@router.patch("/admin/projects/{project_id}/status", response_model=Project, response_model_by_alias=False)
async def update_project_status(
    project_id: str,
    status: ProjectStatus,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fast status transition for a project (draft/published/archived)."""
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"status": status.value, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")

    doc = await db.projects.find_one({"_id": ObjectId(project_id)})
    return Project.from_mongo(doc)


@router.delete("/projects/{project_id}")
@router.delete("/admin/projects/{project_id}")
async def delete_project(
    project_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Deletes a project record."""
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.projects.delete_one({"_id": ObjectId(project_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted"}
