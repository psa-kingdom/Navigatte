"""Authentication request and response schemas."""

from typing import Optional
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class AdminUserPublic(BaseModel):
    id: str
    email: str
    role: str
    access_token: Optional[str] = None
