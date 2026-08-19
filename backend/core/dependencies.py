"""FastAPI dependencies for route protection and authorization."""

from bson import ObjectId
from fastapi import HTTPException, Request, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.database import get_database
from core.security import decode_token
from models.admin import AdminUser


def extract_token_from_request(request: Request) -> str:
    """Extracts access token from cookie or Authorization Bearer header."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


async def get_current_admin(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AdminUser:
    """Dependency that verifies the requesting user is an active authenticated admin."""
    token = extract_token_from_request(request)
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    try:
        user_id = ObjectId(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user identifier")

    doc = await db.admin_users.find_one({"_id": user_id})
    if not doc:
        raise HTTPException(status_code=401, detail="Admin not found")

    return AdminUser.from_mongo(doc)
