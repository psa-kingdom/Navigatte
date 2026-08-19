"""Project (Case Study) document models and enums."""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import List, Optional
from pydantic import BaseModel, Field
from models.base import BaseDocument


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


def generate_slug(title: str) -> str:
    """Generates a URL-safe slug from a project title."""
    cleaned = re.sub(r"[^\w\s-]", "", title.lower()).strip()
    return re.sub(r"[-\s]+", "-", cleaned)


PREDEFINED_TAGS = [
    "Website",
    "Web App",
    "SaaS",
    "Marketing",
    "SAP",
    "Workflow Automation",
]


class ProjectSEO(BaseModel):
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class Project(BaseDocument):
    title: str
    slug: str = Field(default="")
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context):
        if not self.slug and self.title:
            self.slug = generate_slug(self.title)
