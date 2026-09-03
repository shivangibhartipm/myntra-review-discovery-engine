"""Phase 2 — Relevance filter (lexical gate + local judge)."""

from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path

from review_engine.config import AppConfig
from review_engine.db import (
    get_enrichment,
    iter_raw_documents,
    relevance_yield_by_source,
    upsert_enrichment_relevance,
)
from review_engine.eval_gold import evaluate_gold
from review_engine.ollama_client import ollama_available
from review_engine.relevance.pipeline import classify_text
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
    del collected_at, bounds, run_id
    sources = source_filter or None
    use_llm = config.filter.use_llm and ollama_available(config.models.ollama_host)
    judge = None
    if not use_llm:
        from review_engine.relevance.judge import heuristic_judge

        judge = lambda text, lexical, _h=heuristic_judge: _h(text, lexical, config)

    counts_in = 0
    relevant_out = 0
    errors = 0
    gated = 0
    skipped_version = 0
    relevant_samples: list[dict] = []
    rejected_samples: list[dict] = []

    for row in iter_raw_documents(conn, sources):
        counts_in += 1
        existing = get_enrichment(conn, row["doc_id"])
        if (
            config.filter.skip_if_same_version
            and existing is not None
            and existing["filter_version"] == config.filter.version
        ):
            skipped_version += 1
            if existing["is_relevant"]:
                relevant_out += 1
            continue
        try:
            decision = classify_text(row["text"] or "", config, judge=judge)
        except Exception:
            errors += 1
            continue
        if decision.gated:
            gated += 1
        upsert_enrichment_relevance(
            conn,
            doc_id=row["doc_id"],
            is_relevant=decision.is_relevant,
            relevance_score=decision.relevance_score,
            relevance_reasons=decision.relevance_reasons,
            filter_version=decision.filter_version,
        )
        if decision.is_relevant:
            relevant_out += 1
            _maybe_sample(relevant_samples, row, decision)
        else:
            _maybe_sample(rejected_samples, row, decision)

    conn.commit()
    _write_audit_sample(config.filter.sample_path, relevant_samples, rejected_samples)
    gold = evaluate_gold(config, judge=judge)
    yields = relevance_yield_by_source(conn)
    report = {
        "filter_version": config.filter.version,
        "llm_used": use_llm,
        "judge": "llm" if use_llm else "heuristic",
        "counts_in": counts_in,
        "gated": gated,
        "relevant": relevant_out,
        "skipped_same_version": skipped_version,
        "error_count": errors,
        "yield_by_source": yields,
        "gold": gold,
        "audit_sample": str(config.filter.sample_path),
    }
    return counts_in, relevant_out, errors, json.dumps(report)


def _maybe_sample(bucket: list[dict], row, decision, cap: int = 20) -> None:
    item = {
        "doc_id": row["doc_id"],
        "source": row["source"],
        "observed_at": row["observed_at"],
        "text": (row["text"] or "")[:400],
        "is_relevant": decision.is_relevant,
        "score": decision.relevance_score,
        "reasons": list(decision.relevance_reasons),
    }
    if len(bucket) < cap:
        bucket.append(item)
        return
    # reservoir so the 20 are not only the newest
    i = random.randint(0, cap * 5)
    if i < cap:
        bucket[i] = item


def _write_audit_sample(path: Path, relevant: list[dict], rejected: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"relevant": relevant[:20], "rejected": rejected[:20]}, indent=2),
        encoding="utf-8",
    )
