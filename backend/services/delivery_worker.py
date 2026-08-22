"""Durable Outbox Delivery Worker for the Email Management System (EMS).

Implements MongoDB-backed atomic claim/lock semantics, exponential backoff retry scheduling,
transient vs permanent failure classification, campaign metric rollup, and a persistent
run_forever() loop for FastAPI lifespan integration. Replaceable by Redis/RQ/Celery if scale
requirements change.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import settings
from integrations.contracts.communications import (
    CommunicationsProvider,
    EmailMessage,
    EmailRecipient,
)
from integrations.resend.provider import ResendCommunicationsProvider
from models.communications import OutboxItemModel, OutboxStatus
from services.communications_service import CommunicationsService

logger = logging.getLogger(__name__)

LOCK_DURATION_SECONDS = 120  # Claim lock expires after 2 minutes if process crashes

# Terminal statuses — once an item is in these states, it doesn't need processing
_TERMINAL_STATUSES = {
    OutboxStatus.SENT.value,
    OutboxStatus.DELIVERED.value,
    OutboxStatus.BOUNCED.value,
    OutboxStatus.COMPLAINED.value,
    OutboxStatus.OPENED.value,
    OutboxStatus.CLICKED.value,
    OutboxStatus.PROVIDER_DISABLED.value,
}


class DeliveryWorker:
    """Durable queue processor for outbound email delivery."""

    def __init__(self, provider: Optional[CommunicationsProvider] = None):
        self.provider = provider or ResendCommunicationsProvider()

    async def claim_next_item(self, db: AsyncIOMotorDatabase) -> Optional[OutboxItemModel]:
        """Atomically claims one pending or retryable outbox record using find_one_and_update."""
        now = datetime.now(timezone.utc)
        lock_expiry = now + timedelta(seconds=LOCK_DURATION_SECONDS)

        # Condition 1: Queued items waiting for initial dispatch
        # Condition 2: Failed retryable items whose backoff timer has elapsed
        # Condition 3: Stuck "sending" items whose lock has expired (crash recovery)
        query = {
            "$or": [
                {"status": OutboxStatus.QUEUED.value},
                {
                    "status": OutboxStatus.FAILED.value,
                    "is_retryable": True,
                    "attempt_count": {"$lt": 3},
                    "$or": [
                        {"next_attempt_at": {"$lte": now}},
                        {"next_attempt_at": None},
                    ],
                },
                {
                    "status": OutboxStatus.SENDING.value,
                    "lock_expires_at": {"$lte": now},
                },
            ]
        }

        update = {
            "$set": {
                "status": OutboxStatus.SENDING.value,
                "lock_expires_at": lock_expiry,
                "updated_at": now,
            },
            "$inc": {"attempt_count": 1},
        }

        claimed_doc = await db.email_outbox.find_one_and_update(
            query,
            update,
            sort=[("created_at", 1)],
            return_document=True,
        )

        if not claimed_doc:
            return None

        return OutboxItemModel.from_mongo(claimed_doc)

    async def process_item(
        self,
        db: AsyncIOMotorDatabase,
        outbox_item: OutboxItemModel,
    ) -> Dict[str, Any]:
        """Dispatches an individual claimed outbox record and handles state transitions."""
        now = datetime.now(timezone.utc)

        # Guard: If provider is not configured
        if not self.provider.is_enabled():
            await db.email_outbox.update_one(
                {"_id": outbox_item.id},
                {"$set": {
                    "status": OutboxStatus.PROVIDER_DISABLED.value,
                    "error_message": "RESEND_API_KEY is not configured.",
                    "last_error": "Provider unconfigured",
                    "is_retryable": False,
                    "failed_at": now,
                    "updated_at": now,
                }}
            )
            return {"status": "provider_disabled", "outbox_id": outbox_item.id}

        tags = {"template_key": outbox_item.template_key or "custom"}
        if outbox_item.enquiry_id:
            tags["enquiry_id"] = str(outbox_item.enquiry_id)

        # Include campaign_id tag for analytics
        campaign_id = (outbox_item.metadata or {}).get("campaign_id")
        if campaign_id:
            tags["campaign_id"] = str(campaign_id)

        msg = EmailMessage(
            to=[EmailRecipient(email=outbox_item.recipient_email, name=outbox_item.recipient_name)],
            subject=outbox_item.subject,
            html_body=outbox_item.body_html,
            text_body=outbox_item.body_text,
            from_email=outbox_item.from_email,
            idempotency_key=f"{outbox_item.idempotency_key}:worker:{outbox_item.attempt_count}",
            tags=tags,
        )

        try:
            result = await self.provider.send_email(msg)

            if result.status == "sent":
                await db.email_outbox.update_one(
                    {"_id": outbox_item.id},
                    {"$set": {
                        "status": OutboxStatus.SENT.value,
                        "provider_message_id": result.message_id,
                        "sent_at": result.sent_at or now,
                        "error_message": None,
                        "last_error": None,
                        "lock_expires_at": None,
                        "updated_at": now,
                    }}
                )

                # Campaign metric rollup: increment sent_count
                if campaign_id:
                    await self._increment_campaign_sent_count(db, campaign_id)

                return {"status": "sent", "outbox_id": outbox_item.id, "message_id": result.message_id}

            elif result.status == "provider_disabled":
                await db.email_outbox.update_one(
                    {"_id": outbox_item.id},
                    {"$set": {
                        "status": OutboxStatus.PROVIDER_DISABLED.value,
                        "error_message": result.error,
                        "last_error": result.error,
                        "is_retryable": False,
                        "failed_at": now,
                        "lock_expires_at": None,
                        "updated_at": now,
                    }}
                )
                return {"status": "provider_disabled", "outbox_id": outbox_item.id}

            else:
                # Failure during delivery
                error_class = CommunicationsService.classify_error(result.error)
                is_retryable = (error_class == "transient") and (outbox_item.attempt_count < outbox_item.max_attempts)

                # Exponential backoff: 2^(attempts) * 60 seconds (1m, 2m, 4m…)
                backoff_seconds = (2 ** outbox_item.attempt_count) * 60
                next_attempt = now + timedelta(seconds=backoff_seconds) if is_retryable else None

                await db.email_outbox.update_one(
                    {"_id": outbox_item.id},
                    {"$set": {
                        "status": OutboxStatus.FAILED.value,
                        "error_message": result.error,
                        "last_error": result.error,
                        "is_retryable": is_retryable,
                        "next_attempt_at": next_attempt,
                        "failed_at": now,
                        "lock_expires_at": None,
                        "updated_at": now,
                    }}
                )
                return {"status": "failed", "outbox_id": outbox_item.id, "is_retryable": is_retryable}

        except Exception as e:
            logger.error(f"Unexpected worker exception during outbox dispatch {outbox_item.id}: {e}")
            is_retryable = outbox_item.attempt_count < outbox_item.max_attempts
            await db.email_outbox.update_one(
                {"_id": outbox_item.id},
                {"$set": {
                    "status": OutboxStatus.FAILED.value,
                    "error_message": str(e),
                    "last_error": str(e),
                    "is_retryable": is_retryable,
                    "failed_at": now,
                    "lock_expires_at": None,
                    "updated_at": now,
                }}
            )
            return {"status": "error", "outbox_id": outbox_item.id, "error": str(e)}

    async def process_batch(
        self,
        db: AsyncIOMotorDatabase,
        batch_size: int = 10,
    ) -> Dict[str, Any]:
        """Pulls and processes up to batch_size items from the durable queue."""
        processed = 0
        succeeded = 0
        failed = 0
        disabled = 0
        campaign_ids_processed: set = set()

        for _ in range(batch_size):
            item = await self.claim_next_item(db)
            if not item:
                break

            processed += 1
            res = await self.process_item(db, item)
            st = res.get("status")

            # Track which campaigns had items processed this batch
            campaign_id = (item.metadata or {}).get("campaign_id")
            if campaign_id:
                campaign_ids_processed.add(campaign_id)

            if st == "sent":
                succeeded += 1
            elif st == "provider_disabled":
                disabled += 1
            else:
                failed += 1

        # Check if any processed campaigns are now fully complete
        for campaign_id in campaign_ids_processed:
            await self._check_campaign_completion(db, campaign_id)

        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "disabled": disabled,
        }

    async def _increment_campaign_sent_count(self, db: AsyncIOMotorDatabase, campaign_id: str) -> None:
        """Atomically increments the sent_count for a campaign."""
        try:
            await db.campaigns.update_one(
                {"_id": campaign_id},
                {"$inc": {"sent_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}}
            )
        except Exception as e:
            logger.warning(f"[DeliveryWorker] Failed to increment campaign sent_count for {campaign_id}: {e}")

    async def _check_campaign_completion(self, db: AsyncIOMotorDatabase, campaign_id: str) -> None:
        """Checks if all outbox items for a campaign are in terminal states.
        
        If so, transitions the campaign status to COMPLETED.
        """
        try:
            from models.campaign import CampaignStatus

            # Count non-terminal outbox items for this campaign
            non_terminal_count = await db.email_outbox.count_documents({
                "metadata.campaign_id": campaign_id,
                "status": {"$nin": list(_TERMINAL_STATUSES)},
            })

            if non_terminal_count == 0:
                # All items are in terminal state
                campaign_doc = await db.campaigns.find_one({"_id": campaign_id})
                if campaign_doc and campaign_doc.get("status") == "sending":
                    now = datetime.now(timezone.utc)
                    await db.campaigns.update_one(
                        {"_id": campaign_id, "status": "sending"},
                        {"$set": {
                            "status": CampaignStatus.COMPLETED.value,
                            "completed_at": now,
                            "updated_at": now,
                        }}
                    )
                    logger.info(f"[DeliveryWorker] Campaign {campaign_id} transitioned to COMPLETED.")
        except Exception as e:
            logger.warning(f"[DeliveryWorker] Campaign completion check failed for {campaign_id}: {e}")

    async def run_forever(
        self,
        db: AsyncIOMotorDatabase,
        poll_interval: int = 10,
        shutdown_event: Optional[asyncio.Event] = None,
    ) -> None:
        """Runs the delivery worker in a persistent loop.
        
        Designed for use with FastAPI lifespan background tasks. Polls for
        queued outbox items, processes them, and sleeps between batches.
        Exits cleanly when shutdown_event is set.
        
        Args:
            db: Database connection
            poll_interval: Seconds to wait when no items are queued
            shutdown_event: asyncio.Event that signals graceful shutdown
        """
        logger.info("[DeliveryWorker] run_forever() started.")
        while True:
            if shutdown_event and shutdown_event.is_set():
                break
            try:
                result = await self.process_batch(db, batch_size=10)
                sleep_s = 1 if result.get("processed", 0) > 0 else poll_interval
            except Exception as exc:
                logger.error(f"[DeliveryWorker] Exception in run_forever: {exc}")
                sleep_s = 30

            if shutdown_event:
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=sleep_s)
                    break  # Shutdown event was set
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(sleep_s)

        logger.info("[DeliveryWorker] run_forever() exiting.")
