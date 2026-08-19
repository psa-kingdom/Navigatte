"""Admin user document model."""

from datetime import datetime, timezone
from pydantic import Field
from models.base import BaseDocument


class AdminUser(BaseDocument):
    email: str
    password_hash: str
    role: str = "admin"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
