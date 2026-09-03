"""PII policy (fail closed).

Do not persist: author display name, email, avatar URL, IP, or unhashed user ids.
source_native_id is the review/post id (opaque), not a person identifier.
If a payload includes author_id / user_id / handle, hash or drop it.

Text bodies may still contain emails or phones; redact those before insert.
Quotes in later exports must pass the same scan.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\-\s()]{8,}\d)")

DROP_KEYS = {
    "author",
    "author_name",
    "authordisplayname",
    "display_name",
    "email",
    "handle",
    "username",
    "user_name",
    "userimage",
    "user_image",
    "avatar",
    "avatar_url",
    "ip",
    "ip_address",
}

HASH_KEYS = {
    "author_id",
    "user_id",
    "reviewer_id",
    "account_id",
}


def hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def redact_text(text: str) -> str:
    text = EMAIL_RE.sub("[redacted-email]", text)
    text = PHONE_RE.sub("[redacted-phone]", text)
    return text.strip()


def contains_pii(text: str) -> bool:
    return bool(EMAIL_RE.search(text) or PHONE_RE.search(text))


def scrub_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Drop identity fields; hash remaining user ids."""
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        lk = key.lower()
        if lk in DROP_KEYS:
            continue
        if lk in HASH_KEYS and value is not None:
            cleaned[key] = hash_identifier(str(value))
            continue
        cleaned[key] = value
    return cleaned
