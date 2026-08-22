"""Audience and Suppression Domain Models for EMS."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field
import uuid


class AudienceModel(BaseModel):
    """Static or segmented list of recipients for campaigns."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    member_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None

    def to_mongo(self) -> Dict[str, Any]:
        return {
            "_id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "member_count": self.member_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "AudienceModel":
        if not data:
            return None
        from core.datetime_utils import normalize_doc_datetimes
        doc = normalize_doc_datetimes(dict(data))
        doc["id"] = str(doc.pop("_id", data.get("id")))
        return cls(**doc)


class AudienceContactModel(BaseModel):
    """Individual contact assigned to an audience."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audience_id: str
    email: EmailStr
    name: Optional[str] = None
    company: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    is_suppressed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> Dict[str, Any]:
        return {
            "_id": self.id,
            "audience_id": self.audience_id,
            "email": self.email,
            "name": self.name,
            "company": self.company,
            "attributes": self.attributes,
            "is_suppressed": self.is_suppressed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "AudienceContactModel":
        if not data:
            return None
        from core.datetime_utils import normalize_doc_datetimes
        doc = normalize_doc_datetimes(dict(data))
        doc["id"] = str(doc.pop("_id", data.get("id")))
        return cls(**doc)


class SuppressionRecordModel(BaseModel):
    """Global suppression record preventing delivery to bounced/complained/unsubscribed emails."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    reason: str  # 'unsubscribed' | 'hard_bounce' | 'complaint' | 'manual'
    source: Optional[str] = None  # 'resend_webhook' | 'admin_manual' | 'public_unsubscribe'
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None

    def to_mongo(self) -> Dict[str, Any]:
        return {
            "_id": self.id,
            "email": self.email.lower().strip(),
            "reason": self.reason,
            "source": self.source,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "SuppressionRecordModel":
        if not data:
            return None
        from core.datetime_utils import normalize_doc_datetimes
        doc = normalize_doc_datetimes(dict(data))
        doc["id"] = str(doc.pop("_id", data.get("id")))
        return cls(**doc)

