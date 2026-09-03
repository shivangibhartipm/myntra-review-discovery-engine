from __future__ import annotations

from datetime import datetime

from review_engine.collect import collect_from_adapter
from review_engine.config import AppConfig
from review_engine.sources.registry import enabled_adapters
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
    if source_filter:
        adapters = {k: v for k, v in adapters.items() if k in source_filter}
    else:
        adapters = {k: v for k, v in adapters.items() if k == "stub"}
    if not adapters:
        return 0, 0, 0, "no stub adapter enabled for Phase 0"

    counts_in = counts_out = errors = 0
    used = []
    for name, adapter in adapters.items():
        stats = collect_from_adapter(
            conn,
            adapter,
            config=config,
            run_id=run_id,
            collected_at=collected_at,
            bounds=bounds,
        )
        counts_in += stats.counts_in
        counts_out += stats.counts_out
        errors += stats.error_count
        used.append(name)

    notes = f"phase0 stub collect sources={used} sqlite_mvp=true"
    return counts_in, counts_out, errors, notes
