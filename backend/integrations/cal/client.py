"""Cal.com API v2 Client.

Provides server-side API interactions for webhook synchronization, booking retrieval,
and integration diagnostics without leaking credentials to client-side.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx
from core.config import settings

logger = logging.getLogger(__name__)

CAL_API_V2_BASE = "https://api.cal.com/v2"

DEFAULT_WEBHOOK_TRIGGERS = [
    "BOOKING_CREATED",
    "BOOKING_RESCHEDULED",
    "BOOKING_CANCELLED",
    "BOOKING_REJECTED",
    "MEETING_STARTED",
    "MEETING_ENDED",
]


class CalApiClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = CAL_API_V2_BASE):
        self.api_key = api_key or settings.CAL_API_KEY
        self.base_url = base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("Cal.com API Key is not configured.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "cal-api-version": "2024-08-13",
        }

    async def list_webhooks(self) -> List[Dict[str, Any]]:
        """Lists active webhooks from Cal.com API v2."""
        if not self.is_configured:
            return []

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/webhooks", headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    # Cal.com API v2 wraps responses in {"status": "success", "data": [...]}
                    return data.get("data", data) if isinstance(data, dict) else data
                logger.warning(f"Failed to list Cal.com webhooks: HTTP {resp.status_code} - {resp.text}")
                return []
            except Exception as e:
                logger.error(f"Error connecting to Cal.com API: {e}")
                return []

    async def create_webhook(
        self,
        subscriber_url: str,
        secret: Optional[str] = None,
        triggers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Registers a new webhook endpoint with Cal.com."""
        if not self.is_configured:
            raise ValueError("Cal.com API Key is not configured.")

        payload = {
            "subscriberUrl": subscriber_url,
            "triggers": triggers or DEFAULT_WEBHOOK_TRIGGERS,
            "active": True,
        }
        if secret:
            payload["secret"] = secret

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/webhooks",
                headers=self._get_headers(),
                json=payload,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            raise RuntimeError(f"Cal.com webhook registration failed: {resp.status_code} - {resp.text}")

    async def sync_webhook(
        self,
        subscriber_url: str,
        secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Inspects existing webhooks and creates/updates only when necessary."""
        if not self.is_configured:
            return {
                "status": "disabled",
                "message": "Cal.com API Key is not configured. Webhooks must be configured manually in Cal.com dashboard.",
                "subscriber_url": subscriber_url,
            }

        existing_webhooks = await self.list_webhooks()
        matching = next(
            (w for w in existing_webhooks if isinstance(w, dict) and w.get("subscriberUrl") == subscriber_url),
            None,
        )

        if matching:
            return {
                "status": "active",
                "message": "Webhook already registered and active on Cal.com account.",
                "webhook_id": matching.get("id"),
                "subscriber_url": subscriber_url,
                "triggers": matching.get("triggers", DEFAULT_WEBHOOK_TRIGGERS),
            }

        # Create new webhook subscription
        created = await self.create_webhook(subscriber_url=subscriber_url, secret=secret)
        return {
            "status": "created",
            "message": "Successfully registered new webhook on Cal.com account.",
            "subscriber_url": subscriber_url,
            "details": created,
        }
