"""Synthetic source so Phase 0 can write a valid raw_documents row without live APIs."""

from __future__ import annotations

from datetime import datetime, timedelta

from review_engine.pii import scrub_payload
from review_engine.records import CanonicalDocument, build_canonical
from review_engine.sources.base import Page, SourceAdapter
from review_engine.windows import Cutoffs

_SAMPLES = [
    {
        "id": "stub-1",
        "url": "https://example.invalid/reviews/stub-1",
        "days_ago": 12,
        "rating": 4,
        "lang": "en",
        "product_or_category": "ethnic wear",
        "author_name": "Priya S",
        "email": "priya@example.com",
        "text": (
            "Added this kurta to my wishlist until EORS. "
            "Will buy after the sale — contact me at wait@example.com if stock returns."
        ),
    },
    {
        "id": "stub-2",
        "url": "https://example.invalid/reviews/stub-2",
        "days_ago": 40,
        "rating": 3,
        "lang": "en",
        "product_or_category": "footwear",
        "text": "Confused between two pairs on my shortlist. Size chart is unclear so I have not ordered.",
    },
    {
        "id": "stub-3",
        "url": "https://example.invalid/reviews/stub-3",
        "days_ago": 5,
        "rating": 5,
        "lang": "hi",
        "product_or_category": "western wear",
        "text": "Saved for later, waiting for salary. Looks different in haul videos so postponing the buy.",
    },
]


class StubAdapter(SourceAdapter):
    name = "stub"

    def respect_robots_or_tos(self, url: str | None) -> bool:
        # Synthetic data; no live fetch. Live adapters must fail closed.
        return True

    def fetch_page(self, cursor: str | None) -> Page:
        if cursor == "done":
            return Page(items=[], next_cursor=None, exhausted=True)
        return Page(items=list(_SAMPLES), next_cursor="done", exhausted=True)

    def normalize(self, raw: dict, *, collected_at: datetime, bounds: Cutoffs) -> CanonicalDocument:
        payload = scrub_payload(raw)
        observed = collected_at - timedelta(days=int(payload.get("days_ago") or 0))
        return build_canonical(
            source=self.name,
            collected_at=collected_at,
            bounds=bounds,
            text=str(payload["text"]),
            source_native_id=str(payload.get("id")) if payload.get("id") else None,
            url=payload.get("url"),
            observed_at=observed,
            lang=payload.get("lang"),
            rating=float(payload["rating"]) if payload.get("rating") is not None else None,
            product_or_category=payload.get("product_or_category"),
        )
