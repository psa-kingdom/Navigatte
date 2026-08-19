"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.config import settings
from core.database import get_database
from core.dependencies import get_current_admin
from core.security import (
    check_brute_force,
    clear_login_attempts,
    create_access_token,
    create_refresh_token,
    record_failed_login,
    verify_password,
)
from models.admin import AdminUser
from schemas.auth import AdminUserPublic, LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AdminUserPublic)
async def admin_login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    email = payload.email.lower().strip()
    await check_brute_force(db, email)

    doc = await db.admin_users.find_one({"email": email})
    if not doc or not verify_password(payload.password, doc.get("password_hash", "")):
        await record_failed_login(db, email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await clear_login_attempts(db, email)
    admin = AdminUser.from_mongo(doc)
    access_token = create_access_token(admin.id, admin.email)
    refresh_token = create_refresh_token(admin.id)

    cookie_args = settings.cookie_kwargs()
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_MINUTES * 60,
        **cookie_args,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        **cookie_args,
    )

    return AdminUserPublic(
        id=admin.id,
        email=admin.email,
        role=admin.role,
        access_token=access_token,
    )


@router.post("/logout")
async def admin_logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}


@router.get("/me", response_model=AdminUserPublic)
async def admin_me(admin: AdminUser = Depends(get_current_admin)):
    return AdminUserPublic(id=admin.id, email=admin.email, role=admin.role)
