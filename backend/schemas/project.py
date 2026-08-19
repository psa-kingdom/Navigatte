"""Project request and response schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field
from models.project import ProjectStatus, ProjectSEO


class ProjectCreate(BaseModel):
    title: str
    slug: Optional[str] = None
    client_name: Optional[str] = None
    description: str
    content_summary: Optional[str] = None
    image_url: str
    gallery_urls: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    industry_slug: Optional[str] = None
    service_slug: Optional[str] = None
    featured: bool = False
    order: int = 0
    status: ProjectStatus = ProjectStatus.PUBLISHED
    seo: Optional[ProjectSEO] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    client_name: Optional[str] = None
    description: Optional[str] = None
    content_summary: Optional[str] = None
    image_url: Optional[str] = None
    gallery_urls: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    highlights: Optional[List[str]] = None
    industry_slug: Optional[str] = None
    service_slug: Optional[str] = None
    featured: Optional[bool] = None
    order: Optional[int] = None
    status: Optional[ProjectStatus] = None
    seo: Optional[ProjectSEO] = None
