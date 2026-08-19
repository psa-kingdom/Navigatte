"""Navigatte FastAPI Backend Application Entry Point."""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from core.config import settings
from core.database import close_mongo_connection, connect_to_mongo, get_database
from routers import api_router
from services.seeder import seed_admin, seed_demo_projects

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("navigatte.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown hooks."""
    logger.info("Initializing Navigatte API application...")
    try:
        await connect_to_mongo()
        db_instance = get_database()
        await seed_admin(db_instance)
        await seed_demo_projects(db_instance)
    except Exception as e:
        logger.warning(f"Database initialization warning during startup: {e}")
    yield
    logger.info("Shutting down Navigatte API application...")
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