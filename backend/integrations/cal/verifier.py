"""Cal.com Webhook HMAC-SHA256 Signature Verification.

Validates the x-cal-signature-256 header against the raw request body bytes.
"""

import hashlib
import hmac
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

SIGNATURE_HEADER_KEY = "x-cal-signature-256"


def verify_cal_signature(
    raw_body: bytes,
    headers: Dict[str, str],
    webhook_secret: Optional[str],
    is_production: bool = True,
) -> bool:
    """Verifies that the HMAC-SHA256 digest of raw_body matches the x-cal-signature-256 header.

    Args:
        raw_body: Exact raw bytes of the incoming HTTP request.
        headers: Dict of incoming HTTP headers (case-insensitive search).
        webhook_secret: The configured CAL_WEBHOOK_SECRET.
        is_production: Boolean indicating whether running in production.

    Returns:
        bool: True if signature is valid, False otherwise.
    """
    if not webhook_secret:
        if is_production:
            logger.error("CAL_WEBHOOK_SECRET is missing in production. Rejecting unverified webhook.")
            return False
        logger.warning("CAL_WEBHOOK_SECRET is not configured in development. Allowing unverified webhook.")
        return True

    # Case-insensitive header extraction
    signature: Optional[str] = None
    for k, v in headers.items():
        if k.lower() == SIGNATURE_HEADER_KEY:
            signature = v.strip()
            break

    if not signature:
        logger.warning(f"Webhook rejected: Missing {SIGNATURE_HEADER_KEY} header.")
        return False

    # Compute HMAC-SHA256 over raw_body bytes
    try:
        computed_digest = hmac.new(
            key=webhook_secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(computed_digest.lower(), signature.lower())
        if not is_valid:
            logger.warning("Webhook rejected: HMAC-SHA256 signature mismatch.")
        return is_valid
    except Exception as e:
        logger.error(f"Error computing webhook signature: {e}")
        return False
