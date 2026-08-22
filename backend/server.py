"""Navigatte FastAPI Backend Application Entry Point."""

import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from core.config import settings
from core.database import (
    close_mongo_connection,
    connect_to_mongo,
    ensure_communications_indexes,
    get_database,
)
from routers import api_router
from services.seeder import seed_admin, seed_demo_projects

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("navigatte.api")

# Global shutdown event for graceful worker termination
_shutdown_event = asyncio.Event()


async def _run_delivery_worker() -> None:
    """Persistent background delivery worker loop.

    Polls the MongoDB outbox for queued/retryable items and dispatches them
    through Resend.  Runs as an asyncio background task inside the FastAPI
    lifespan so that Railway's single-dyno setup keeps the worker alive
    alongside the web server.

    Design invariants:
    - Restart-safe: worker starts fresh on every process restart.
    - Lock-safe: MongoDB atomic find_one_and_update prevents double-claiming.
    - No duplicate sends: idempotency_key on each outbox item.
    - Graceful shutdown: exits cleanly when _shutdown_event is set.
    - Provider isolation: provider errors update outbox state; they never
      crash the worker loop.
    """
    from services.delivery_worker import DeliveryWorker

    worker = DeliveryWorker()
    logger.info("[DeliveryWorker] Background delivery loop started.")

    while not _shutdown_event.is_set():
        try:
            db = get_database()
            result = await worker.process_batch(db, batch_size=10)
            # If we processed items, loop again quickly; otherwise back off
            sleep_seconds = 1 if result.get("processed", 0) > 0 else 10
        except Exception as exc:
            logger.error(f"[DeliveryWorker] Unhandled exception in worker loop: {exc}")
            sleep_seconds = 30  # Back off on unexpected errors

        try:
            # Wait for either the sleep interval or a shutdown signal
            await asyncio.wait_for(_shutdown_event.wait(), timeout=sleep_seconds)
        except asyncio.TimeoutError:
            pass  # Normal: sleep elapsed, continue looping

    logger.info("[DeliveryWorker] Shutdown signal received — background loop exiting.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown hooks."""
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    logger.info("Initializing Navigatte API application...")
    worker_task = None

    try:
        await connect_to_mongo()
        db_instance = get_database()
        await seed_admin(db_instance)
        await seed_demo_projects(db_instance)

        # Ensure all Communications collection indexes exist
        await ensure_communications_indexes(db_instance)

        # Start the persistent delivery worker as a background asyncio task
        worker_task = asyncio.create_task(_run_delivery_worker(), name="delivery-worker")
        logger.info("[DeliveryWorker] Background task created and running.")

    except Exception as e:
        logger.warning(f"Database initialization warning during startup: {e}")

    yield

    # ---- Shutdown ----
    logger.info("Shutting down Navigatte API application...")
    _shutdown_event.set()

    if worker_task and not worker_task.done():
        try:
            await asyncio.wait_for(worker_task, timeout=15)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            logger.warning("[DeliveryWorker] Worker did not stop cleanly within timeout; cancelling.")
            worker_task.cancel()

    try:
        await close_mongo_connection()
    except Exception:
        pass


# Create FastAPI application
app = FastAPI(
    title="Navigatte API",
    description="Enterprise Technology, Automation & Digital Platforms API",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS middleware safely
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes under /api
app.include_router(api_router)

# Backward-compatibility reference for legacy imports (e.g. from server import db)
db = get_database()