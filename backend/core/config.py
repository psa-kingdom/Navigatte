"""Application configuration and settings.
Centralizes environment variable loading with safety checks for production."""

import logging
import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger(__name__)


class Settings:
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", os.getenv("RAILWAY_ENVIRONMENT", "development"))
    IS_PRODUCTION: bool = ENVIRONMENT.lower() in ("production", "prod")

    # Database
    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "navigatte_dev")

    # Authentication & Tokens
    _raw_jwt_secret: Optional[str] = os.getenv("JWT_SECRET")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 60 * 12  # 12 hours
    REFRESH_TOKEN_DAYS: int = 7
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    # Admin Seeding
    ADMIN_EMAIL: Optional[str] = os.getenv("ADMIN_EMAIL")
    ADMIN_PASSWORD: Optional[str] = os.getenv("ADMIN_PASSWORD")

    @property
    def JWT_SECRET(self) -> str:
        if self._raw_jwt_secret:
            return self._raw_jwt_secret
        if self.IS_PRODUCTION:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: JWT_SECRET environment variable is missing in production!"
            )
        logger.warning(
            "JWT_SECRET is not set. Using insecure default key for local development only."
        )
        return "supersecretlocaldevelopmentsignedkey321!"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        raw = os.getenv("CORS_ORIGINS", "")
        if raw:
            origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
            if "*" in origins:
                logger.warning("CORS_ORIGINS contains '*' which is invalid with allow_credentials=True. Removing '*'.")
                origins = [o for o in origins if o != "*"]
            if origins:
                return origins

        # Default local origins
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    def cookie_kwargs(self) -> dict:
        return {
            "httponly": True,
            "secure": self.IS_PRODUCTION,
            "samesite": "lax",
            "path": "/",
        }


settings = Settings()
