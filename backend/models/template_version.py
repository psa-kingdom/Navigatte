"""Email Template Versioning Model."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class EmailTemplateVersionModel(BaseModel):
    """Immutable snapshot of an email template at a specific version."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    template_id: str
    template_key: str
    version: int
    name: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    change_summary: Optional[str] = None

    def to_mongo(self) -> Dict[str, Any]:
        return {
            "_id": self.id,
            "template_id": self.template_id,
            "template_key": self.template_key,
            "version": self.version,
            "name": self.name,
            "subject": self.subject,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "variables": self.variables,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "change_summary": self.change_summary,
        }

    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "EmailTemplateVersionModel":
        if not data:
            return None
        doc = dict(data)
        doc["id"] = str(doc.pop("_id", data.get("id")))
        return cls(**doc)
