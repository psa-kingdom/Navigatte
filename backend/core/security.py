"""Security, cryptography, JWT token handling, and brute-force protection."""

from datetime import datetime, timedelta, timezone
import logging
import bcrypt
import jwt
from fastapi import HTTPException
from core.config import settings

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def check_brute_force(db, identifier: str):
    """Checks if an identifier (admin email) is currently locked out."""
    record = await db.login_attempts.find_one({"identifier": identifier})
    if record and record.get("count", 0) >= settings.MAX_LOGIN_ATTEMPTS:
        locked_until = record.get("locked_until")
        if locked_until:
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed login attempts. Try again later.",
                )


async def record_failed_login(db, identifier: str):
    """Increments failed login count and triggers lockout if threshold is exceeded."""
    record = await db.login_attempts.find_one({"identifier": identifier})
    count = (record.get("count", 0) if record else 0) + 1
    locked_until = None
    if count >= settings.MAX_LOGIN_ATTEMPTS:
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.LOCKOUT_MINUTES)
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$set": {"count": count, "locked_until": locked_until}},
        upsert=True,
    )


async def clear_login_attempts(db, identifier: str):
    """Clears failed login attempt counter upon successful authentication."""
    await db.login_attempts.delete_one({"identifier": identifier})
