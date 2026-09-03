"""Phase 6 — Insight delivery (static report + board artifacts)."""

from __future__ import annotations

import json
from datetime import datetime

from review_engine.config import AppConfig
from review_engine.present.pipeline import present_opportunities
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
    del run_id, source_filter
    report = present_opportunities(conn, config=config, bounds=bounds, collected_at=collected_at)
    return report["counts_in"], report["counts_out"], 0, json.dumps(report)
