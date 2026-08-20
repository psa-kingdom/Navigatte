"""Campaign Domain Models for the Email Management System (EMS)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field
import uuid


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class CampaignModel(BaseModel):
    """EMS Campaign domain entity representing an email marketing or outreach initiative."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    environment: str = "test"  # 'test' | 'production'
    sender_email: str = "Navigatte <updates@updates.navigatte.com>"
    reply_to: Optional[str] = None
    subject: str
    template_key: str
    template_version: int = 1
    audience_id: Optional[str] = None
    audience_source: str = "audience"  # 'newsletter' | 'manual' | 'both' | 'audience'
    manual_recipients: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)  # Emails or domains to exclude e.g. '@navigatte.com'
    custom_html: Optional[str] = None
    status: CampaignStatus = CampaignStatus.DRAFT
    test_recipients: List[EmailStr] = Field(default_factory=list)  # Hard boundary for test environment
    
    # Recipient and Telemetry Metrics
    total_recipients: int = 0
    sent_count: int = 0
    delivered_count: int = 0
    bounced_count: int = 0
    opened_count: int = 0
    clicked_count: int = 0
    complained_count: int = 0
    failed_count: int = 0
    
    # Lifecycle Timestamps
    scheduled_at: Optional[datetime] = None
    launched_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    
    # Validation Checklist State
    launch_checklist: Dict[str, Any] = Field(default_factory=dict)

    def to_mongo(self) -> Dict[str, Any]:
        return {
            "_id": self.id,
            "name": self.name,
            "description": self.description,
            "environment": self.environment,
            "sender_email": self.sender_email,
            "reply_to": self.reply_to,
            "subject": self.subject,
            "template_key": self.template_key,
            "template_version": self.template_version,
            "audience_id": self.audience_id,
            "audience_source": self.audience_source,
            "manual_recipients": self.manual_recipients,
            "exclusions": self.exclusions,
            "custom_html": self.custom_html,
            "status": self.status.value if isinstance(self.status, CampaignStatus) else str(self.status),
            "test_recipients": self.test_recipients,
            "total_recipients": self.total_recipients,
            "sent_count": self.sent_count,
            "delivered_count": self.delivered_count,
            "bounced_count": self.bounced_count,
            "opened_count": self.opened_count,
            "clicked_count": self.clicked_count,
            "complained_count": self.complained_count,
            "failed_count": self.failed_count,
            "scheduled_at": self.scheduled_at,
            "launched_at": self.launched_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "launch_checklist": self.launch_checklist,
        }

    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "CampaignModel":
        if not data:
            return None
        doc = dict(data)
        doc["id"] = str(doc.pop("_id", data.get("id")))
        return cls(**doc)
