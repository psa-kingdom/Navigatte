"""Communications Audit Logging Model."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import uuid


class CommunicationsAuditLogModel(BaseModel):
    """Audit log entry capturing administrative and lifecycle actions in EMS."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    actor_email: str
    action: str  # e.g. 'template_created', 'campaign_launched', 'email_retried', 'suppression_added'
    target_type: str  # 'template' | 'campaign' | 'outbox' | 'audience' | 'suppression'
    target_id: str
    environment: str = "test"
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_mongo(self) -> Dict[str, Any]:
        return {
            "_id": self.id,
            "actor_email": self.actor_email,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "environment": self.environment,
            "details": self.details,
            "created_at": self.created_at,
        }

    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "CommunicationsAuditLogModel":
        if not data:
            return None
        from core.datetime_utils import normalize_doc_datetimes
        doc = normalize_doc_datetimes(dict(data))
        doc["id"] = str(doc.pop("_id", data.get("id")))
        return cls(**doc)

