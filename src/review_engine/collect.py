from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from review_engine.config import AppConfig
from review_engine.db import document_exists, get_checkpoint, upsert_checkpoint, upsert_document
from review_engine.lang import detect_lang, should_keep_lang
from review_engine.sources.base import SourceAdapter
from review_engine.windows import Cutoffs

CURSOR_DONE = "done"


@dataclass
class CollectStats:
    counts_in: int = 0
    counts_out: int = 0
    error_count: int = 0
    duplicates: int = 0
    skipped_window: int = 0
    skipped_lang: int = 0
    skipped_tos: int = 0
    skipped_empty: int = 0
    mode: str = "backfill"
    truncated: bool = False

    def as_dict(self) -> dict:
        return {
            "counts_in": self.counts_in,
            "counts_out": self.counts_out,
            "error_count": self.error_count,
            "duplicates": self.duplicates,
            "skipped_window": self.skipped_window,
            "skipped_lang": self.skipped_lang,
            "skipped_tos": self.skipped_tos,
            "skipped_empty": self.skipped_empty,
            "mode": self.mode,
            "truncated": self.truncated,
            "duplicate_rate": (self.duplicates / self.counts_in) if self.counts_in else 0.0,
        }


def collect_from_adapter(
    conn,
    adapter: SourceAdapter,
    *,
    config: AppConfig,
    run_id: str,
    collected_at: datetime,
    bounds: Cutoffs,
    quota: int | None = None,
) -> CollectStats:
    del config
    stats = CollectStats()
    remaining = quota if quota is not None else adapter.config.daily_quota
    saved_cursor, saved_last = get_checkpoint(conn, adapter.name)

    if saved_cursor == CURSOR_DONE:
        stats.mode = "incremental"
        start_cursor = None
        stop_at = saved_last
    else:
        stats.mode = "backfill"
        start_cursor = saved_cursor
        stop_at = bounds.primary_start

    last_observed = saved_last
    last_cursor = start_cursor
    newest_seen = saved_last
    hit_floor = False
    stopped_for_quota = False

    try:
        for page in adapter.iter_pages(start_cursor):
            last_cursor = page.next_cursor
            for raw in page.items:
                if remaining <= 0:
                    stopped_for_quota = True
                    break
                stats.counts_in += 1
                remaining -= 1
                url = raw.get("url") if isinstance(raw, dict) else None
                try:
                    if not adapter.respect_robots_or_tos(url):
                        stats.skipped_tos += 1
                        stats.error_count += 1
                        continue
                    doc = adapter.normalize(raw, collected_at=collected_at, bounds=bounds)
                    if not doc.text:
                        stats.skipped_empty += 1
                        continue
                    doc.lang = detect_lang(doc.text, hinted=doc.lang)
                    if not should_keep_lang(doc.lang):
                        stats.skipped_lang += 1
                        continue
                    if doc.observed_at is None:
                        stats.error_count += 1
                        continue
                    if stats.mode == "incremental" and stop_at and doc.observed_at <= stop_at:
                        hit_floor = True
                        stats.skipped_window += 1
                        break
                    if doc.observed_at < bounds.primary_start:
                        stats.skipped_window += 1
                        if adapter.newest_first:
                            hit_floor = True
                            break
                        continue
                    if document_exists(conn, doc.doc_id):
                        stats.duplicates += 1
                        upsert_document(conn, doc, run_id)
                    else:
                        upsert_document(conn, doc, run_id)
                        stats.counts_out += 1
                    if newest_seen is None or doc.observed_at > newest_seen:
                        newest_seen = doc.observed_at
                    last_observed = newest_seen
                except Exception:
                    stats.error_count += 1
            if remaining <= 0:
                stopped_for_quota = True
                break
            if hit_floor:
                break
    except KeyboardInterrupt:
        upsert_checkpoint(conn, adapter.name, last_cursor or start_cursor, newest_seen or last_observed)
        conn.commit()
        raise

    if stats.mode == "incremental":
        cursor_out = CURSOR_DONE
    elif stopped_for_quota and not hit_floor:
        cursor_out = last_cursor
        stats.truncated = True
    else:
        cursor_out = CURSOR_DONE
        stats.truncated = stats.truncated or bool(getattr(adapter, "truncated", False))

    upsert_checkpoint(conn, adapter.name, cursor_out, newest_seen or last_observed)
    conn.commit()
    return stats
