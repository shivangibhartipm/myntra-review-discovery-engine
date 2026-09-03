from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from review_engine.config import CANONICAL_SOURCES
from review_engine.pii import redact_text
from review_engine.windows import assign_corpus_layer, Cutoffs


@dataclass
class CanonicalDocument:
    """Minimum fields after Phase 1; Phase 0 stub must produce a valid row."""

    doc_id: str
    source: str
    source_native_id: str | None
    url: str | None
    observed_at: datetime | None
    collected_at: datetime
    text: str
    lang: str | None
    rating: float | None
    thread_id: str | None
    product_or_category: str | None
    corpus_layer: str | None

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["observed_at"] = self.observed_at.isoformat(timespec="seconds") if self.observed_at else None
        row["collected_at"] = self.collected_at.isoformat(timespec="seconds")
        return row


def make_doc_id(
    source: str,
    source_native_id: str | None,
    url: str | None,
    observed_at: datetime | None,
) -> str:
    stamp = observed_at.isoformat(timespec="seconds") if observed_at else ""
    payload = f"{source}|{source_native_id or ''}|{url or ''}|{stamp}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def build_canonical(
    *,
    source: str,
    collected_at: datetime,
    bounds: Cutoffs,
    text: str,
    source_native_id: str | None = None,
    url: str | None = None,
    observed_at: datetime | None = None,
    lang: str | None = None,
    rating: float | None = None,
    thread_id: str | None = None,
    product_or_category: str | None = None,
) -> CanonicalDocument:
    if source not in CANONICAL_SOURCES:
        raise ValueError(f"unknown source {source!r}")
    body = redact_text(text)
    if not body:
        raise ValueError("text is empty after PII redaction")
    return CanonicalDocument(
        doc_id=make_doc_id(source, source_native_id, url, observed_at),
        source=source,
        source_native_id=source_native_id,
        url=url,
        observed_at=observed_at,
        collected_at=collected_at,
        text=body,
        lang=lang,
        rating=rating,
        thread_id=thread_id,
        product_or_category=product_or_category,
        corpus_layer=assign_corpus_layer(source, observed_at, bounds),
    )
