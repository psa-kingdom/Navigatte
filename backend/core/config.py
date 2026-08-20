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

    # Cookie Settings
    COOKIE_SAMESITE: Optional[str] = os.getenv("COOKIE_SAMESITE")
    COOKIE_SECURE: Optional[str] = os.getenv("COOKIE_SECURE")

    # Cal.com Scheduling Integration
    CAL_ENABLED: bool = os.getenv("CAL_ENABLED", "false").lower() in ("true", "1", "yes")
    CAL_WEBHOOK_SECRET: Optional[str] = os.getenv("CAL_WEBHOOK_SECRET")
    CAL_EVENT_TYPE_ID: Optional[str] = os.getenv("CAL_EVENT_TYPE_ID")
    CAL_WEBHOOK_SUBSCRIBER_URL: Optional[str] = os.getenv("CAL_WEBHOOK_SUBSCRIBER_URL")

    # Resend Communications Integration
    RESEND_ENABLED: bool = os.getenv("RESEND_ENABLED", "false").lower() in ("true", "1", "yes")
    RESEND_API_KEY: Optional[str] = os.getenv("RESEND_API_KEY")
    RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "Navigatte <updates@updates.navigatte.com>")
    RESEND_WEBHOOK_SECRET: Optional[str] = os.getenv("RESEND_WEBHOOK_SECRET")

    @property
    def CAL_API_KEY(self) -> Optional[str]:
        return (
            os.getenv("CAL_API_KEY")
            or os.getenv("CAL_COM_API")
            or os.getenv("CALCOM_API_KEY")
        )

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
        configured = []
        if raw:
            origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
            if "*" in origins:
                logger.warning("CORS_ORIGINS contains '*' which is invalid with allow_credentials=True. Removing '*'.")
                origins = [o for o in origins if o != "*"]
            configured = origins

        # Standard known origins (local dev + production custom domains)
        standard_origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://navigatte.com",
            "https://www.navigatte.com",
            "https://navigatte-website.vercel.app",
        ]

        # Combine configured + standard, deduplicating while preserving order
        combined = list(dict.fromkeys(configured + standard_origins))
        return combined

    @property
    def CORS_ORIGIN_REGEX(self) -> Optional[str]:
        raw = os.getenv("CORS_ORIGIN_REGEX")
        if raw is not None:
            raw_clean = raw.strip()
            return raw_clean if raw_clean else None
        # Default scoped regex strictly for Navigatte Vercel preview deployments
        # Matches:
        #   https://navigatte-website-*.vercel.app within the psumanassociates-9980s-projects team namespace
        #   https://navigatte-website-git-*.vercel.app
        #   https://navigatte-*.vercel.app within the team namespace
        return r"^https:\/\/(navigatte-website|navigatte)(-[a-z0-9-]+)?-psumanassociates-9980s-projects\.vercel\.app$"

    def cookie_kwargs(self) -> dict:
        # For cross-site frontend-backend deployments (e.g. Vercel -> Railway over HTTPS),
        # SameSite=None + Secure=True is required for browsers to accept and send session cookies.
        # In local HTTP development, SameSite=Lax + Secure=False is used.
        if self.COOKIE_SAMESITE:
            samesite = self.COOKIE_SAMESITE.lower()
        else:
            samesite = "none" if self.IS_PRODUCTION else "lax"

        if self.COOKIE_SECURE is not None:
            secure = self.COOKIE_SECURE.lower() in ("true", "1")
        else:
            secure = True if self.IS_PRODUCTION or samesite == "none" else False

        return {
            "httponly": True,
            "secure": secure,
            "samesite": samesite,
            "path": "/",
        }


settings = Settings()
