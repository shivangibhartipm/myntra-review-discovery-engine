"""Phase 1 — Collect and structure public reviews into raw_documents."""

from __future__ import annotations

import json
from datetime import datetime

from review_engine.collect import CollectStats, collect_from_adapter
from review_engine.config import AppConfig
from review_engine.db import counts_by_source_and_layer
from review_engine.sources.registry import PHASE1_SOURCES, enabled_adapters
from review_engine.windows import Cutoffs


def run(
    conn,
    *,
    config: AppConfig,
    run_id: str,
    collected_at: datetime,
    bounds: Cutoffs,
    source_filter: list[str],
) -> tuple[int, int, int, str]:
    adapters = enabled_adapters(config)
    wanted = set(source_filter) if source_filter else set(PHASE1_SOURCES)
    adapters = {k: v for k, v in adapters.items() if k in wanted and k in PHASE1_SOURCES}

    skipped: list[str] = []
    per_source: dict[str, dict] = {}
    totals = CollectStats()

    if not adapters:
        report = {
            "skipped": ["no P0/P1 adapters enabled"],
            "per_source": {},
            **counts_by_source_and_layer(conn),
        }
        return 0, 0, 0, json.dumps(report)

    for name, adapter in adapters.items():
        ok, reason = adapter.is_available()
        if not ok:
            skipped.append(f"{name}: {reason}")
            continue
        stats = collect_from_adapter(
            conn,
            adapter,
            config=config,
            run_id=run_id,
            collected_at=collected_at,
            bounds=bounds,
        )
        per_source[name] = stats.as_dict()
        totals.counts_in += stats.counts_in
        totals.counts_out += stats.counts_out
        totals.error_count += stats.error_count
        totals.duplicates += stats.duplicates
        totals.skipped_window += stats.skipped_window
        totals.skipped_lang += stats.skipped_lang

    corpus = counts_by_source_and_layer(conn)
    report = {
        "phase": "collect",
        "windows": bounds.as_dict(),
        "skipped": skipped,
        "per_source": per_source,
        "totals": {
            "counts_in": totals.counts_in,
            "counts_out": totals.counts_out,
            "error_count": totals.error_count,
            "duplicates": totals.duplicates,
            "duplicate_rate": (totals.duplicates / totals.counts_in) if totals.counts_in else 0.0,
        },
        **corpus,
    }
    return totals.counts_in, totals.counts_out, totals.error_count, json.dumps(report)
