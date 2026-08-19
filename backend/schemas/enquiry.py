"""Enquiry request and response schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from models.enquiry import EnquiryStatus, EnquiryNote


class EnquiryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=30)
    company: Optional[str] = Field(None, max_length=120)
    service_interest: Optional[str] = Field(None, max_length=100)
    message: str = Field(..., min_length=5, max_length=5000)
    source: Optional[str] = "website_contact"
    website_hp: Optional[str] = Field(None, description="Honeypot field for bot detection")


class EnquiryPublicResponse(BaseModel):
    success: bool = True
    message: str = "Thank you for contacting Navigatte. We have received your enquiry and will respond within 24 hours."


class EnquiryStatusUpdate(BaseModel):
    status: EnquiryStatus


class EnquiryNoteCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=3000)
