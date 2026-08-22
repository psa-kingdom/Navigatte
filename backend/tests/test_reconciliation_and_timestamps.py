"""Post-Delivery Production Reconciliation & Timestamp Regression Test Suite."""

import pytest
from datetime import datetime, timezone
from core.database import get_database
from core.datetime_utils import ensure_utc, normalize_doc_datetimes
from models.communications import OutboxItemModel, OutboxStatus
from models.campaign import CampaignModel
from models.audit import CommunicationsAuditLogModel
from services.communications_service import CommunicationsService


def test_datetime_utils_ensure_utc_naive_conversion():
    """Naive datetimes from PyMongo are assigned timezone.utc."""
    naive_dt = datetime(2026, 8, 22, 18, 31, 0)
    aware = ensure_utc(naive_dt)
    assert aware.tzinfo == timezone.utc
    assert aware.year == 2026
    assert aware.hour == 18


def test_datetime_utils_normalize_doc_datetimes():
    """Recursive normalization turns all naive datetimes into aware UTC datetimes."""
    doc = {
        "created_at": datetime(2026, 8, 22, 18, 31, 0),
        "nested": {
            "sent_at": datetime(2026, 8, 22, 18, 32, 0),
            "count": 5,
        },
        "history": [
            {"attempt_at": datetime(2026, 8, 22, 18, 33, 0)},
            "plain_string",
        ],
    }
    normalized = normalize_doc_datetimes(doc)
    assert normalized["created_at"].tzinfo == timezone.utc
    assert normalized["nested"]["sent_at"].tzinfo == timezone.utc
    assert normalized["history"][0]["attempt_at"].tzinfo == timezone.utc


def test_outbox_model_from_mongo_utc_iso_serialization():
    """OutboxItemModel.from_mongo outputs ISO-8601 strings with explicit UTC timezone offset."""
    raw_doc = {
        "_id": "outbox_test_123",
        "idempotency_key": "idem_123",
        "recipient_email": "test@navigatte.com",
        "subject": "Test Advisory",
        "body_html": "<p>Content</p>",
        "created_at": datetime(2026, 8, 22, 18, 31, 0),  # Naive as returned by Motor
        "sent_at": datetime(2026, 8, 22, 18, 31, 5),
    }
    model = OutboxItemModel.from_mongo(raw_doc)
    dumped = model.model_dump(mode="json")

    # Verify explicit UTC offset (either 'Z' or '+00:00')
    assert dumped["created_at"].endswith("Z") or "+00:00" in dumped["created_at"]
    assert dumped["sent_at"].endswith("Z") or "+00:00" in dumped["sent_at"]


def test_campaign_model_from_mongo_utc_iso_serialization():
    """CampaignModel.from_mongo outputs ISO-8601 strings with explicit UTC timezone offset."""
    raw_doc = {
        "_id": "camp_test_123",
        "name": "Q3 Briefing",
        "subject": "Important Briefing",
        "custom_html": "<p>Hello</p>",
        "created_at": datetime(2026, 8, 22, 18, 31, 0),
        "launched_at": datetime(2026, 8, 22, 18, 32, 0),
    }
    model = CampaignModel.from_mongo(raw_doc)
    dumped = model.model_dump(mode="json")
    assert dumped["created_at"].endswith("Z") or "+00:00" in dumped["created_at"]
    assert dumped["launched_at"].endswith("Z") or "+00:00" in dumped["launched_at"]


def test_audit_model_from_mongo_utc_iso_serialization():
    """CommunicationsAuditLogModel.from_mongo outputs explicit UTC offsets."""
    raw_doc = {
        "_id": "audit_123",
        "actor_email": "admin@navigatte.com",
        "action": "campaign_launched",
        "target_type": "campaign",
        "target_id": "camp_123",
        "created_at": datetime(2026, 8, 22, 18, 31, 0),
    }
    model = CommunicationsAuditLogModel.from_mongo(raw_doc)
    dumped = model.model_dump(mode="json")
    assert dumped["created_at"].endswith("Z") or "+00:00" in dumped["created_at"]


@pytest.mark.asyncio
async def test_retry_guards_prevent_duplicate_delivery(client, auth_headers):
    """Guards prevent re-sending already delivered or in-flight outbox items."""
    db = get_database()
    now = datetime.now(timezone.utc)
    service = CommunicationsService()

    # 1. Delivered item guard
    delivered_doc = {
        "_id": "delivered_item_1",
        "idempotency_key": "idem_deliv_1",
        "recipient_email": "client@enterprise.com",
        "subject": "Delivered message",
        "body_html": "<p>Delivered</p>",
        "status": OutboxStatus.DELIVERED.value,
        "attempt_count": 1,
        "max_attempts": 3,
        "created_at": now,
    }
    await db.email_outbox.insert_one(delivered_doc)

    with pytest.raises(ValueError, match="already delivered"):
        await service.retry_outbox_item(db, "delivered_item_1")

    # 2. Maximum attempts guard
    maxed_doc = {
        "_id": "maxed_item_1",
        "idempotency_key": "idem_max_1",
        "recipient_email": "failed@enterprise.com",
        "subject": "Failed message",
        "body_html": "<p>Failed</p>",
        "status": OutboxStatus.FAILED.value,
        "attempt_count": 3,
        "max_attempts": 3,
        "created_at": now,
    }
    await db.email_outbox.insert_one(maxed_doc)

    with pytest.raises(ValueError, match="maximum retry attempts"):
        await service.retry_outbox_item(db, "maxed_item_1")
