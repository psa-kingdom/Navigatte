"""Public Unsubscribe Endpoint.

Provides a signed HMAC-SHA256 token-based unsubscribe flow that creates
a suppression record and returns an HTML confirmation page. No authentication
required — this is a public endpoint accessed from email footers.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Depends

from core.database import get_database
from services.communications_service import CommunicationsService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["unsubscribe"])

_UNSUBSCRIBE_SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Unsubscribed — Navigatte</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f172a;
      color: #cbd5e1;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0;
      padding: 24px;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 16px;
      padding: 48px 40px;
      max-width: 480px;
      width: 100%;
      text-align: center;
    }}
    .icon {{
      width: 56px;
      height: 56px;
      background: #10b981;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 24px;
      font-size: 28px;
    }}
    h1 {{ color: #f1f5f9; font-size: 1.5rem; margin: 0 0 12px; font-weight: 600; }}
    p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.6; margin: 0; }}
    .email {{ color: #e2e8f0; font-weight: 500; }}
    .footer {{ margin-top: 32px; font-size: 0.8rem; color: #475569; }}
    a {{ color: #6366f1; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✓</div>
    <h1>You've been unsubscribed</h1>
    <p>
      The address <span class="email">{email}</span> has been removed from
      Navigatte marketing communications.
    </p>
    <p style="margin-top: 12px;">
      You may still receive transactional emails related to active services or consultations.
    </p>
    <div class="footer">
      <a href="https://navigatte.com">navigatte.com</a>
    </div>
  </div>
</body>
</html>"""

_UNSUBSCRIBE_ERROR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Unsubscribe Error — Navigatte</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f172a;
      color: #cbd5e1;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0;
      padding: 24px;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 16px;
      padding: 48px 40px;
      max-width: 480px;
      width: 100%;
      text-align: center;
    }}
    .icon {{
      width: 56px; height: 56px;
      background: #ef4444;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 24px; font-size: 28px;
    }}
    h1 {{ color: #f1f5f9; font-size: 1.5rem; margin: 0 0 12px; font-weight: 600; }}
    p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.6; margin: 0; }}
    a {{ color: #6366f1; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✗</div>
    <h1>Link expired or invalid</h1>
    <p>
      {reason}<br /><br />
      Please <a href="mailto:support@navigatte.com">contact support</a> if you
      continue to receive unwanted emails and we will manually suppress your address.
    </p>
  </div>
</body>
</html>"""


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(
    email: str = Query(..., description="Email address to unsubscribe"),
    token: str = Query(..., description="HMAC-SHA256 unsubscribe token"),
    exp: int = Query(..., description="Token expiry Unix timestamp"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> HTMLResponse:
    """Public unsubscribe endpoint. Called from email footer links.
    
    Validates the signed HMAC-SHA256 token, creates a suppression record,
    and returns an HTML confirmation page. Expired or invalid tokens return
    an error page.
    
    Token generation: CommunicationsService.generate_unsubscribe_token(email)
    Token validation: CommunicationsService.verify_unsubscribe_token(email, token, exp)
    """
    clean_email = email.lower().strip()

    # Validate token
    is_valid = CommunicationsService.verify_unsubscribe_token(
        email=clean_email,
        token=token,
        expires_at=exp,
    )

    if not is_valid:
        import time
        if int(time.time()) > exp:
            reason = (
                "This unsubscribe link has expired (links are valid for 30 days). "
                "If you received a recent email, use the unsubscribe link in that message instead."
            )
        else:
            reason = "This unsubscribe link is invalid or has been tampered with."

        logger.warning(
            f"[Unsubscribe] Invalid/expired token for email={clean_email} exp={exp}"
        )
        return HTMLResponse(
            content=_UNSUBSCRIBE_ERROR_HTML.format(reason=reason),
            status_code=400,
        )

    # Create suppression record (idempotent upsert)
    now = datetime.now(timezone.utc)
    try:
        await db.email_suppressions.update_one(
            {"email": clean_email},
            {"$setOnInsert": {
                "email": clean_email,
                "reason": "unsubscribed",
                "source": "email_link",
                "created_at": now,
            }},
            upsert=True,
        )

        # Mark all audience contacts with this email as suppressed
        await db.audience_contacts.update_many(
            {"email": clean_email},
            {"$set": {"is_suppressed": True}}
        )

        logger.info(f"[Unsubscribe] {clean_email} → added to email_suppressions via signed link.")

        # Audit log
        await db.communications_audit_logs.insert_one({
            "actor_email": clean_email,
            "action": "unsubscribed",
            "target_type": "suppression",
            "target_id": clean_email,
            "details": {"source": "email_link", "reason": "unsubscribed"},
            "created_at": now,
        })

    except Exception as e:
        logger.error(f"[Unsubscribe] DB error for {clean_email}: {e}")
        return HTMLResponse(
            content=_UNSUBSCRIBE_ERROR_HTML.format(
                reason="A system error occurred while processing your unsubscribe request. Please try again later."
            ),
            status_code=500,
        )

    return HTMLResponse(
        content=_UNSUBSCRIBE_SUCCESS_HTML.format(email=clean_email),
        status_code=200,
    )
