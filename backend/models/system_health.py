"""System Health and Integration Status Data Models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
    NOT_CONFIGURED = "not_configured"
    DISABLED = "disabled"
    MONITORING_UNAVAILABLE = "monitoring_unavailable"
    UNKNOWN = "unknown"


class IntegrationCategory(str, Enum):
    SCHEDULING = "scheduling"
    COMMUNICATIONS = "communications"
    DATABASE = "database"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"


class IntegrationHealthRecord(BaseModel):
    """Provider-agnostic structured health and diagnostic report."""
    provider: str  # e.g. "cal.com", "resend", "mongodb", "railway", "vercel"
    category: IntegrationCategory
    display_name: str
    enabled: bool = True
    configured: bool = False
    status: HealthStatus = HealthStatus.UNKNOWN
    connectivity: str = "unknown"  # "connected", "unreachable", "unconfigured", "runtime_active"
    latency_ms: Optional[float] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_event_at: Optional[datetime] = None
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    affected_capabilities: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    documentation_url: Optional[str] = None
    can_test: bool = False
    can_reconnect: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SystemHealthOverview(BaseModel):
    """Overall platform health and diagnostics roll-up."""
    overall_status: HealthStatus
    system_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    environment: str = "production"
    version: str = "2.2.0"
    integrations: List[IntegrationHealthRecord] = Field(default_factory=list)
    recent_incidents: List[Dict[str, Any]] = Field(default_factory=list)
    recent_events: List[Dict[str, Any]] = Field(default_factory=list)
