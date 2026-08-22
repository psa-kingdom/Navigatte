"""Resend API Client.

Performs server-side API interactions with Resend REST API (v1) using httpx.
Does not require external heavy SDKs or introduce fragile dependencies.
"""

import logging
import re
from typing import Any, Dict, List, Optional
import httpx
from core.config import settings

logger = logging.getLogger(__name__)

RESEND_API_BASE = "https://api.resend.com"


def _clean_resend_tag(val: Any) -> Optional[str]:
    """Sanitizes a tag name or value according to Resend validation rules.
    
    Resend rule: 'Tags should only contain ASCII letters, numbers, underscores, or dashes.'
    Empty strings or special characters are omitted or sanitized.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    cleaned = re.sub(r'[^a-zA-Z0-9_-]', '_', s)
    return cleaned if cleaned else None


class ResendApiClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = RESEND_API_BASE,
    ):
        self.api_key = api_key or getattr(settings, "RESEND_API_KEY", None)
        self.base_url = base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("Resend API Key is not configured.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_email(
        self,
        to: List[str],
        subject: str,
        from_email: Optional[str] = None,
        html: Optional[str] = None,
        text: Optional[str] = None,
        reply_to: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Dispatches an outbound email through Resend API."""
        if not self.is_configured:
            raise ValueError("Resend API Key is not configured.")

        default_from = getattr(settings, "RESEND_FROM_EMAIL", "Navigatte <updates@updates.navigatte.com>")
        payload: Dict[str, Any] = {
            "from": from_email or default_from,
            "to": to,
            "subject": subject,
        }
        if html:
            payload["html"] = html
            if not text:
                # Generate clean plain text from html for high-deliverability multipart email
                clean_text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.I)
                clean_text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', clean_text, flags=re.I)
                clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                payload["text"] = clean_text
        if text:
            payload["text"] = text
        if reply_to:
            payload["reply_to"] = reply_to
        if tags:
            cleaned_tags = []
            for k, v in tags.items():
                clean_k = _clean_resend_tag(k)
                clean_v = _clean_resend_tag(v)
                if clean_k and clean_v:
                    cleaned_tags.append({"name": clean_k, "value": clean_v})
            if cleaned_tags:
                payload["tags"] = cleaned_tags

        # Auto-extract List-Unsubscribe header from HTML if present
        all_headers = dict(headers or {})
        if html and "List-Unsubscribe" not in all_headers:
            unsub_match = re.search(r'href=[\'"]([^\'"]*api/unsubscribe[^\'"]*)[\'"]', html, flags=re.I)
            if unsub_match:
                unsub_url = unsub_match.group(1)
                all_headers["List-Unsubscribe"] = f"<{unsub_url}>"
                all_headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        if all_headers:
            payload["headers"] = all_headers

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                f"{self.base_url}/emails",
                headers=self._get_headers(),
                json=payload,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            raise RuntimeError(f"Resend email dispatch failed: HTTP {resp.status_code} - {resp.text}")

    async def get_email(self, email_id: str) -> Dict[str, Any]:
        """Retrieves email metadata and delivery status from Resend."""
        if not self.is_configured:
            raise ValueError("Resend API Key is not configured.")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.base_url}/emails/{email_id}",
                headers=self._get_headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"Failed to retrieve email {email_id}: HTTP {resp.status_code} - {resp.text}")
