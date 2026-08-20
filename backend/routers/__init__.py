"""API Routers."""

from fastapi import APIRouter
from routers.auth import router as auth_router
from routers.projects import router as projects_router
from routers.enquiries import router as enquiries_router
from routers.status import router as status_router
from routers.webhooks import router as webhooks_router
from routers.integrations import router as integrations_router
from routers.admin_search import router as admin_search_router
from routers.system_health import router as system_health_router

api_router = APIRouter(prefix="/api")
api_router.include_router(status_router)
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(enquiries_router)
api_router.include_router(webhooks_router)
api_router.include_router(integrations_router)
api_router.include_router(admin_search_router)
api_router.include_router(system_health_router)

__all__ = [
    "api_router",
    "auth_router",
    "projects_router",
    "enquiries_router",
    "status_router",
    "webhooks_router",
    "integrations_router",
    "admin_search_router",
    "system_health_router",
]
