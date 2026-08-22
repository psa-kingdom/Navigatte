"""Database client and lifecycle management."""

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from core.config import settings

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None


def get_database() -> AsyncIOMotorDatabase:
    """Returns the current database instance."""
    global db, client
    if db is None:
        client = AsyncIOMotorClient(settings.MONGO_URL, serverSelectionTimeoutMS=2000)
        db = client[settings.DB_NAME]
    return db


async def connect_to_mongo():
    """Establishes connection to MongoDB and sets up database reference."""
    global client, db
    if db is not None:
        return
    logger.info(f"Connecting to MongoDB at {settings.MONGO_URL}...")
    client = AsyncIOMotorClient(settings.MONGO_URL, serverSelectionTimeoutMS=2000)
    db = client[settings.DB_NAME]
    logger.info(f"Connected to database: {settings.DB_NAME}")
    await init_db_indexes()


async def close_mongo_connection():
    """Closes MongoDB connection."""
    global client
    if client:
        logger.info("Closing MongoDB connection...")
        client.close()
        logger.info("MongoDB connection closed.")


async def init_db_indexes():
    """Initializes required unique and search indexes."""
    global db
    if db is None:
        return
    try:
        # Admin Users
        await db.admin_users.create_index("email", unique=True)

        # Login attempts (brute-force monitoring)
        await db.login_attempts.create_index("identifier", unique=True)

        # Projects
        await db.projects.create_index([("status", 1), ("featured", 1), ("order", 1)])
        await db.projects.create_index("slug", unique=False)

        # Enquiries
        await db.enquiries.create_index([("status", 1), ("created_at", -1)])
        await db.enquiries.create_index("email")
        await db.enquiries.create_index([("is_test", 1), ("status", 1)])

        # Integration Webhook Events (Idempotency & Auditing)
        await db.integration_webhook_events.create_index("idempotency_key", unique=True)
        await db.integration_webhook_events.create_index([("provider", 1), ("received_at", -1)])
        await db.integration_webhook_events.create_index("external_booking_uid")

        # Classify existing RCA diagnostic lead as test data if present
        await db.enquiries.update_many(
            {"email": {"$regex": "^rca_verification_test@", "$options": "i"}},
            {"$set": {"is_test": True}},
        )

        logger.info("Database indexes initialized successfully.")
    except Exception as e:
        logger.warning(f"Index initialization warning: {e}")


async def ensure_communications_indexes(db: AsyncIOMotorDatabase):
    """Creates required indexes for all EMS/Communications collections.
    
    These were identified as missing in the forensic audit. Without these,
    queue polling degrades as the outbox grows, and idempotency enforcement
    relies on application-level checks only.
    """
    try:
        from pymongo import ASCENDING, DESCENDING

        # Outbox: idempotency deduplication (prevents duplicate sends)
        await db.email_outbox.create_index("idempotency_key", unique=True, background=True)

        # Outbox: delivery worker queue polling (status + next_attempt_at compound)
        await db.email_outbox.create_index(
            [("status", ASCENDING), ("next_attempt_at", ASCENDING)],
            background=True,
        )

        # Outbox: webhook matching by provider message ID
        await db.email_outbox.create_index("provider_message_id", background=True, sparse=True)

        # Outbox: created_at sort for list views
        await db.email_outbox.create_index([("created_at", DESCENDING)], background=True)

        # Suppressions: unique email (idempotent upserts)
        await db.email_suppressions.create_index("email", unique=True, background=True)

        # Audience contacts: compound unique (prevents duplicate imports)
        await db.audience_contacts.create_index(
            [("audience_id", ASCENDING), ("email", ASCENDING)],
            unique=True,
            background=True,
        )

        # Campaigns: sort by created_at for list views
        await db.campaigns.create_index([("created_at", DESCENDING)], background=True)

        # Campaigns: status filter
        await db.campaigns.create_index("status", background=True)

        # Templates: key lookup (already unique by app logic, but index helps)
        await db.email_templates.create_index("key", unique=True, background=True)

        # Template versions: lookup by key + version
        await db.email_template_versions.create_index(
            [("template_key", ASCENDING), ("version", DESCENDING)],
            background=True,
        )

        logger.info("[EMS] Communications collection indexes ensured.")
    except Exception as e:
        logger.warning(f"[EMS] Communications index initialization warning: {e}")
