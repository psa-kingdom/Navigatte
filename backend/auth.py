"""Backward-compatibility re-exports for auth module."""

from core.config import settings
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    check_brute_force,
    record_failed_login,
    clear_login_attempts,
)
from core.dependencies import get_current_admin
from services.seeder import seed_admin

JWT_ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_MINUTES = settings.ACCESS_TOKEN_MINUTES
REFRESH_TOKEN_DAYS = settings.REFRESH_TOKEN_DAYS
MAX_LOGIN_ATTEMPTS = settings.MAX_LOGIN_ATTEMPTS
LOCKOUT_MINUTES = settings.LOCKOUT_MINUTES


def get_jwt_secret() -> str:
    return settings.JWT_SECRET


__all__ = [
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_MINUTES",
    "REFRESH_TOKEN_DAYS",
    "MAX_LOGIN_ATTEMPTS",
    "LOCKOUT_MINUTES",
    "get_jwt_secret",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "check_brute_force",
    "record_failed_login",
    "clear_login_attempts",
    "get_current_admin",
    "seed_admin",
]
