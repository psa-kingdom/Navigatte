"""Domain document models."""

from models.base import BaseDocument, PyObjectId
from models.admin import AdminUser
from models.project import Project, ProjectStatus, ProjectSEO, PREDEFINED_TAGS, generate_slug
from models.enquiry import Enquiry, EnquiryStatus, EnquiryNote

__all__ = [
    "BaseDocument",
    "PyObjectId",
    "AdminUser",
    "Project",
    "ProjectStatus",
    "ProjectSEO",
    "PREDEFINED_TAGS",
    "generate_slug",
    "Enquiry",
    "EnquiryStatus",
    "EnquiryNote",
]
