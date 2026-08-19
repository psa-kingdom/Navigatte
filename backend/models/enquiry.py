"""Enquiry (CRM Lead) document models and enums."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field
from models.base import BaseDocument


class EnquiryStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    CLOSED = "closed"


class EnquiryNote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Enquiry(BaseDocument):
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    service_interest: Optional[str] = None
    message: str
    source: str = "website_contact"
    status: EnquiryStatus = EnquiryStatus.NEW
    notes: List[EnquiryNote] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
