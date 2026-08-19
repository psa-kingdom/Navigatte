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

        logger.info("Database indexes initialized successfully.")
    except Exception as e:
        logger.warning(f"Index initialization warning: {e}")
