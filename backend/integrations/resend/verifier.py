"""Resend Webhook Signature Verifier.

Resend uses Svix (v1, HMAC-SHA256) for webhook signatures:
Headers:
- svix-id: Message ID
- svix-timestamp: Timestamp of the message
- svix-signature: Space-delimited signatures, e.g. "v1,g0hM9SvStZA..."
"""

import base64
import hashlib
import hmac
import logging
from typing import Dict, Optional
from core.config import settings

logger = logging.getLogger(__name__)


class ResendWebhookVerifier:
    def __init__(self, secret: Optional[str] = None):
        self.secret = secret or getattr(settings, "RESEND_WEBHOOK_SECRET", None)

    @property
    def is_configured(self) -> bool:
        return bool(self.secret)

    def verify(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        """Verifies Svix / Resend HMAC-SHA256 signature."""
        if not self.is_configured:
            logger.warning("RESEND_WEBHOOK_SECRET is not configured. Webhook rejected.")
            return False

        # Extract Svix headers (case-insensitive)
        headers_lower = {k.lower(): v for k, v in headers.items()}
        msg_id = headers_lower.get("svix-id")
        msg_timestamp = headers_lower.get("svix-timestamp")
        msg_signature = headers_lower.get("svix-signature")

        if not msg_id or not msg_timestamp or not msg_signature:
            logger.warning("Missing Svix signature headers in Resend webhook request.")
            return False

        # Prepare signed content: "{msg_id}.{msg_timestamp}.{raw_body}"
        to_sign = f"{msg_id}.{msg_timestamp}.".encode("utf-8") + raw_body

        # Resend/Svix secrets are prefixed with "whsec_" and base64 encoded
        secret_clean = self.secret.strip()
        if secret_clean.startswith("whsec_"):
            secret_key = base64.b64decode(secret_clean[6:])
        else:
            secret_key = secret_clean.encode("utf-8")

        expected_sig_bytes = hmac.new(secret_key, to_sign, hashlib.sha256).digest()
        expected_b64 = base64.b64encode(expected_sig_bytes).decode("utf-8")

        # Compare against space-separated signatures in header
        passed = False
        for versioned_sig in msg_signature.split(" "):
            parts = versioned_sig.split(",", 1)
            if len(parts) == 2 and parts[0] == "v1":
                if hmac.compare_digest(parts[1], expected_b64):
                    passed = True
                    break

        return passed
