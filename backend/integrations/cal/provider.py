"""Cal.com Scheduling Provider Implementation.

Implements the SchedulingProvider contract to adapt Cal.com v2 webhooks and API
to Navigatte's normalized scheduling domain.
"""

from typing import Any, Dict
from core.config import settings
from integrations.contracts.scheduling import SchedulingEvent, SchedulingProvider
from integrations.cal.client import CalApiClient
from integrations.cal.mapper import map_cal_webhook_to_event
from integrations.cal.verifier import verify_cal_signature


class CalSchedulingProvider(SchedulingProvider):
    """Concrete Cal.com scheduling adapter."""

    def __init__(self):
        self._client = CalApiClient(api_key=settings.CAL_API_KEY)

    @property
    def name(self) -> str:
        return "cal.com"

    def is_enabled(self) -> bool:
        return settings.CAL_ENABLED or bool(settings.CAL_WEBHOOK_SECRET or settings.CAL_API_KEY)

    def verify_webhook_signature(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        return verify_cal_signature(
            raw_body=raw_body,
            headers=headers,
            webhook_secret=settings.CAL_WEBHOOK_SECRET,
            is_production=settings.IS_PRODUCTION,
        )

    def normalize_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> SchedulingEvent:
        return map_cal_webhook_to_event(payload_dict=payload, headers=headers)

    async def sync_webhook(self, subscriber_url: str) -> Dict[str, Any]:
        return await self._client.sync_webhook(
            subscriber_url=subscriber_url,
            secret=settings.CAL_WEBHOOK_SECRET,
        )
