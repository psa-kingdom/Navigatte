"""Canonical UTC Datetime Normalization Utilities for Navigatte API & EMS.

Guarantees:
1. All datetime objects originating from database reads (PyMongo naive BSON datetimes)
   are converted to timezone-aware UTC objects (tzinfo=timezone.utc).
2. ISO-8601 serializations (via Pydantic model_dump, jsonable_encoder, or isoformat)
   always contain the explicit UTC offset ('Z' or '+00:00') so that browser JavaScript
   correctly renders the timestamp in the administrator's local timezone.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List


def ensure_utc(dt: Any) -> Any:
    """Ensures a datetime object is timezone-aware in UTC.
    
    If naive (e.g. returned by PyMongo BSON reader), assigns timezone.utc.
    If already aware, converts to timezone.utc.
    """
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return dt


def normalize_doc_datetimes(doc: Any) -> Any:
    """Recursively converts all datetime values within a dict or list to timezone-aware UTC."""
    if isinstance(doc, dict):
        return {k: normalize_doc_datetimes(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [normalize_doc_datetimes(item) for item in doc]
    elif isinstance(doc, datetime):
        return ensure_utc(doc)
    return doc
