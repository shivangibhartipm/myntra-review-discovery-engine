"""Phase 5 — Quantify, compare, and rank opportunity areas."""

from __future__ import annotations

import json
from datetime import datetime

from review_engine.config import AppConfig
from review_engine.db import (
    apply_opportunity_ranks,
    count_documents,
    count_relevant_documents,
    fetch_opportunity_areas,
    iter_extracted_documents,
)
from review_engine.rank.pipeline import member_from_row, rank_opportunities, volume_order_differs
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
    del collected_at, run_id
    opportunities = [dict(row) for row in fetch_opportunity_areas(conn)]
    if not opportunities:
        report = {
            "rank_version": config.rank.version,
            "message": "no opportunity areas; run --phase cluster first",
            "counts_in": 0,
            "counts_out": 0,
        }
        return 0, 0, 0, json.dumps(report)

    sources = source_filter or None
    members = {row["doc_id"]: member_from_row(row) for row in iter_extracted_documents(conn, sources)}
    n_unfiltered = count_documents(conn)
    n_relevant = count_relevant_documents(conn)
    ranked = rank_opportunities(
        opportunities,
        members,
        n_relevant=n_relevant,
        n_unfiltered=n_unfiltered,
        bounds=bounds,
        weights=config.rank,
    )
    apply_opportunity_ranks(conn, [o.as_dict() for o in ranked])
    conn.commit()
    _write_export(config.rank.export_path, [o.as_dict() for o in ranked])

    top = ranked[: config.rank.top_n_compare]
    report = {
        "rank_version": config.rank.version,
        "weights": config.rank.weights_dict(),
        "counts_in": len(opportunities),
        "counts_out": len(ranked),
        "n_relevant": n_relevant,
        "n_unfiltered": n_unfiltered,
        "volume_order_differs": volume_order_differs(ranked),
        "rank_90d": [
            {
                "rank": o.rank_90d,
                "opportunity_id": o.opportunity_id,
                "rank_score": o.rank_score_90d,
                "metric_relevance": o.metric_relevance,
                "prevalence_relevant": o.prevalence_relevant,
                "prevalence_unfiltered": o.prevalence_unfiltered,
                "postponement_rate": o.postponement_rate,
            }
            for o in top
        ],
        "rank_12m": sorted(
            (
                {
                    "rank": o.rank_12m,
                    "opportunity_id": o.opportunity_id,
                    "rank_score": o.rank_score_12m,
                }
                for o in ranked
            ),
            key=lambda r: r["rank"] or 0,
        )[: config.rank.top_n_compare],
        "export": str(config.rank.export_path),
        "formula": (
            "w1*(metric_relevance/5)+w2*postponement_rate+w3*prevalence_relevant"
            "+w4*recency_90d_share+w5*actionability-w6*loud_but_weak_penalty"
        ),
    }
    return len(opportunities), len(ranked), 0, json.dumps(report)


def _write_export(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
