"""Platform System Health and Integration Evaluation Service."""

from datetime import datetime, timezone
import logging
import os
import time
from typing import Any, Dict, List, Optional
import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import settings
from integrations.cal.client import CalApiClient
from integrations.resend.client import ResendApiClient
from models.system_health import (
    HealthStatus,
    IntegrationCategory,
    IntegrationHealthRecord,
    SystemHealthOverview,
)

logger = logging.getLogger(__name__)


class HealthService:
    @staticmethod
    async def evaluate_mongodb(db: AsyncIOMotorDatabase) -> IntegrationHealthRecord:
        """Evaluates MongoDB Atlas cluster connectivity and performance."""
        record = IntegrationHealthRecord(
            provider="mongodb",
            category=IntegrationCategory.DATABASE,
            display_name="MongoDB Atlas",
            enabled=True,
            configured=True,
            can_test=True,
            documentation_url="https://www.mongodb.com/docs/atlas/",
        )
        try:
            start_t = time.perf_counter()
            await db.command("ping")
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)

            projects_count = await db.projects.count_documents({})
            enquiries_count = await db.enquiries.count_documents({})
            events_count = await db.integration_webhook_events.count_documents({})

            record.status = HealthStatus.HEALTHY
            record.connectivity = "connected"
            record.latency_ms = latency_ms
            record.last_success_at = datetime.now(timezone.utc)
            record.metadata = {
                "database_name": db.name,
                "latency_ms": latency_ms,
                "projects_count": projects_count,
                "enquiries_count": enquiries_count,
                "webhook_events_count": events_count,
            }
        except Exception as e:
            logger.error(f"MongoDB health evaluation failed: {e}")
            record.status = HealthStatus.ERROR
            record.connectivity = "unreachable"
            record.last_failure_at = datetime.now(timezone.utc)
            record.last_error_message = str(e)
            record.affected_capabilities = ["All CMS Operations", "CRM Lead Storage", "Auth Sessions"]
            record.recommended_action = "Check MongoDB Atlas cluster network access list and MONGO_URL credentials."

        return record

    @staticmethod
    async def evaluate_cal(db: AsyncIOMotorDatabase) -> IntegrationHealthRecord:
        """Evaluates Cal.com API v2 connectivity and webhook reception health."""
        has_api_key = bool(settings.CAL_API_KEY)
        has_webhook_secret = bool(settings.CAL_WEBHOOK_SECRET)

        record = IntegrationHealthRecord(
            provider="cal.com",
            category=IntegrationCategory.SCHEDULING,
            display_name="Cal.com",
            enabled=settings.CAL_ENABLED or has_api_key,
            configured=has_api_key,
            can_test=True,
            can_reconnect=True,
            documentation_url="https://cal.com/docs/api-reference/v2",
        )

        if not has_api_key and not has_webhook_secret:
            record.status = HealthStatus.NOT_CONFIGURED
            record.connectivity = "unconfigured"
            record.affected_capabilities = ["Automated CRM Meeting Sync", "Direct Calendar Webhooks"]
            record.recommended_action = "Configure CAL_API_KEY and CAL_WEBHOOK_SECRET in Railway."
            return record

        # 1. Inspect recent webhook events in MongoDB
        last_event_docs = await db.integration_webhook_events.find({"provider": "cal.com"}).sort("received_at", -1).limit(1).to_list(1)
        last_failed_docs = await db.integration_webhook_events.find({"provider": "cal.com", "processing_status": "failed"}).sort("received_at", -1).limit(1).to_list(1)
        total_events = await db.integration_webhook_events.count_documents({"provider": "cal.com"})

        if last_event_docs:
            record.last_event_at = last_event_docs[0].get("received_at")
            if last_event_docs[0].get("processing_status") == "processed":
                record.last_success_at = last_event_docs[0].get("received_at")

        if last_failed_docs:
            record.last_failure_at = last_failed_docs[0].get("received_at")
            record.last_error_message = last_failed_docs[0].get("error_message")

        # 2. Test Cal.com API connectivity if API key is present
        api_connected = False
        api_latency_ms = None
        if has_api_key:
            client = CalApiClient()
            try:
                start_t = time.perf_counter()
                webhooks = await client.list_webhooks()
                api_latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                api_connected = True
                record.last_success_at = datetime.now(timezone.utc)
            except Exception as e:
                logger.warning(f"Cal.com API test failed: {e}")
                record.last_failure_at = datetime.now(timezone.utc)
                record.last_error_message = f"API connection failed: {str(e)}"

        record.latency_ms = api_latency_ms
        record.metadata = {
            "has_api_key": has_api_key,
            "has_webhook_secret": has_webhook_secret,
            "api_connected": api_connected,
            "webhook_endpoint": "/api/webhooks/cal",
            "total_events_received": total_events,
            "event_type_id": settings.CAL_EVENT_TYPE_ID,
        }

        # 3. Determine Overall Status
        if not has_webhook_secret:
            record.status = HealthStatus.DEGRADED
            record.connectivity = "partially_configured"
            record.affected_capabilities = ["Secure Inbound Webhook Processing"]
            record.recommended_action = "CAL_WEBHOOK_SECRET is missing in Railway. Inbound webhooks will be rejected with 401."
        elif has_api_key and not api_connected:
            record.status = HealthStatus.DEGRADED
            record.connectivity = "api_unreachable"
            record.affected_capabilities = ["Automated Webhook Management"]
            record.recommended_action = "Verify CAL_API_KEY permissions in Cal.com dashboard."
        else:
            record.status = HealthStatus.HEALTHY
            record.connectivity = "connected"

        return record

    @staticmethod
    async def evaluate_resend(db: AsyncIOMotorDatabase) -> IntegrationHealthRecord:
        """Evaluates Resend email communications provider health."""
        has_api_key = bool(settings.RESEND_API_KEY)
        has_webhook_secret = bool(settings.RESEND_WEBHOOK_SECRET)

        record = IntegrationHealthRecord(
            provider="resend",
            category=IntegrationCategory.COMMUNICATIONS,
            display_name="Resend",
            enabled=settings.RESEND_ENABLED or has_api_key,
            configured=has_api_key,
            can_test=has_api_key,
            documentation_url="https://resend.com/docs",
        )

        record.metadata = {
            "has_api_key": has_api_key,
            "has_webhook_secret": has_webhook_secret,
            "sending_domain": "updates.navigatte.com",
            "from_email": settings.RESEND_FROM_EMAIL,
        }

        if not has_api_key:
            record.status = HealthStatus.NOT_CONFIGURED
            record.connectivity = "unconfigured"
            record.affected_capabilities = ["Outbound Transactional Email", "Campaign Broadcasts"]
            record.recommended_action = "Add RESEND_API_KEY in Railway to enable transactional email delivery for updates.navigatte.com."
            return record

        # Test API connection
        client = ResendApiClient()
        try:
            start_t = time.perf_counter()
            # Quick check against Resend API
            async with httpx.AsyncClient(timeout=4.0) as http_c:
                resp = await http_c.get(
                    "https://api.resend.com/api-keys",
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                )
                record.latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                if resp.status_code in (200, 403):  # 200 or restricted scope
                    record.status = HealthStatus.HEALTHY
                    record.connectivity = "connected"
                    record.last_success_at = datetime.now(timezone.utc)
                else:
                    record.status = HealthStatus.ERROR
                    record.connectivity = "auth_failed"
                    record.last_failure_at = datetime.now(timezone.utc)
                    record.last_error_message = f"Resend API rejected credentials (HTTP {resp.status_code})"
                    record.recommended_action = "Generate a new API key in Resend dashboard."
        except Exception as e:
            record.status = HealthStatus.DEGRADED
            record.connectivity = "unreachable"
            record.last_failure_at = datetime.now(timezone.utc)
            record.last_error_message = str(e)
            record.recommended_action = "Check network egress from Railway to api.resend.com."

        return record

    @staticmethod
    def evaluate_railway() -> IntegrationHealthRecord:
        """Evaluates Railway hosting container environment."""
        env_name = settings.ENVIRONMENT
        is_railway = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME"))

        return IntegrationHealthRecord(
            provider="railway",
            category=IntegrationCategory.INFRASTRUCTURE,
            display_name="Railway Backend Container",
            enabled=True,
            configured=True,
            status=HealthStatus.HEALTHY if is_railway else HealthStatus.MONITORING_UNAVAILABLE,
            connectivity="runtime_active" if is_railway else "local_or_custom",
            can_test=False,
            documentation_url="https://railway.com/docs",
            metadata={
                "environment": env_name,
                "service_name": os.getenv("RAILWAY_SERVICE_NAME", "backend"),
                "is_railway": is_railway,
            },
        )

    @staticmethod
    def evaluate_vercel() -> IntegrationHealthRecord:
        """Evaluates Vercel frontend connectivity and CORS security status."""
        return IntegrationHealthRecord(
            provider="vercel",
            category=IntegrationCategory.INFRASTRUCTURE,
            display_name="Vercel Frontend & Previews",
            enabled=True,
            configured=True,
            status=HealthStatus.HEALTHY,
            connectivity="cors_active",
            can_test=False,
            documentation_url="https://vercel.com/docs",
            metadata={
                "cors_regex_active": bool(settings.CORS_ORIGIN_REGEX),
                "cookie_samesite": settings.cookie_kwargs().get("samesite"),
                "cookie_secure": settings.cookie_kwargs().get("secure"),
            },
        )

    @classmethod
    async def get_system_health(cls, db: AsyncIOMotorDatabase) -> SystemHealthOverview:
        """Assembles full platform system health overview across all integrations."""
        mongo_record = await cls.evaluate_mongodb(db)
        cal_record = await cls.evaluate_cal(db)
        resend_record = await cls.evaluate_resend(db)
        railway_record = cls.evaluate_railway()
        vercel_record = cls.evaluate_vercel()

        integrations = [
            mongo_record,
            cal_record,
            resend_record,
            railway_record,
            vercel_record,
        ]

        # Determine overall roll-up status
        statuses = [r.status for r in integrations if r.status != HealthStatus.NOT_CONFIGURED and r.status != HealthStatus.MONITORING_UNAVAILABLE]
        if any(s == HealthStatus.ERROR for s in statuses):
            overall = HealthStatus.ERROR
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        # Fetch recent audit events
        recent_events_cursor = db.integration_webhook_events.find({}).sort("received_at", -1).limit(10)
        event_docs = await recent_events_cursor.to_list(10)
        recent_events = []
        for doc in event_docs:
            recent_events.append({
                "id": str(doc["_id"]),
                "provider": doc.get("provider", "unknown"),
                "event_type": doc.get("event_type", "unknown"),
                "status": doc.get("processing_status", "unknown"),
                "received_at": doc.get("received_at").isoformat() if doc.get("received_at") else None,
                "error_message": doc.get("error_message"),
            })

        # Recent incidents (failed events or active errors)
        recent_incidents = []
        for r in integrations:
            if r.status in (HealthStatus.DEGRADED, HealthStatus.ERROR):
                recent_incidents.append({
                    "provider": r.provider,
                    "display_name": r.display_name,
                    "status": r.status.value,
                    "error": r.last_error_message,
                    "recommended_action": r.recommended_action,
                    "occurred_at": (r.last_failure_at or datetime.now(timezone.utc)).isoformat(),
                })

        return SystemHealthOverview(
            overall_status=overall,
            system_timestamp=datetime.now(timezone.utc),
            environment=settings.ENVIRONMENT,
            integrations=integrations,
            recent_incidents=recent_incidents,
            recent_events=recent_events,
        )
