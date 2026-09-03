"""Time windows: analysis uses observed_at; collected_at is ingest-only.

Primary corpus = last 12 months of observed_at.
Recency slice = last 90 days of observed_at (also inside the 12-month set).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from review_engine.config import AppConfig, subtract_months, WindowsConfig

CORPUS_LAYERS = (
    "primary_12m",
    "recency_90d",
    "trend_18_24m",
    "pdp_6_12m",
)


@dataclass(frozen=True)
class Cutoffs:
    as_of: datetime
    recency_start: datetime
    primary_start: datetime
    trend_start: datetime
    trend_end: datetime
    pdp_start: datetime

    def as_dict(self) -> dict[str, str]:
        return {
            "as_of": self.as_of.isoformat(timespec="seconds"),
            "recency_start": self.recency_start.isoformat(timespec="seconds"),
            "primary_start": self.primary_start.isoformat(timespec="seconds"),
            "trend_start": self.trend_start.isoformat(timespec="seconds"),
            "trend_end": self.trend_end.isoformat(timespec="seconds"),
            "pdp_start": self.pdp_start.isoformat(timespec="seconds"),
        }


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def cutoffs(config: AppConfig, collected_at: datetime | None = None) -> Cutoffs:
    """Cutoffs from config windows, anchored at as_of or this run's collected_at."""
    as_of = config.as_of or collected_at or now_utc()
    w: WindowsConfig = config.windows
    return Cutoffs(
        as_of=as_of,
        recency_start=as_of - timedelta(days=w.recency_days),
        primary_start=subtract_months(as_of, w.primary_months),
        trend_start=subtract_months(as_of, w.trend_start_months),
        trend_end=subtract_months(as_of, w.trend_end_months),
        pdp_start=subtract_months(as_of, w.pdp_months),
    )


def assign_corpus_layer(
    source: str,
    observed_at: datetime | None,
    bounds: Cutoffs,
) -> str | None:
    if observed_at is None:
        return None
    if observed_at > bounds.as_of:
        return None
    if observed_at >= bounds.recency_start:
        return "recency_90d"
    if observed_at >= bounds.primary_start:
        return "primary_12m"
    if source == "pdp" and observed_at >= bounds.pdp_start:
        return "pdp_6_12m"
    if bounds.trend_start <= observed_at < bounds.trend_end:
        return "trend_18_24m"
    return None
