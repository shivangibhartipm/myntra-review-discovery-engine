"""Phase 3 — Extract jobs and blockers from relevant documents."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from review_engine.config import AppConfig
from review_engine.db import get_enrichment, iter_relevant_documents, upsert_enrichment_extract
from review_engine.extract.eval import evaluate_extract_gold
from review_engine.extract.pipeline import extract_claim
from review_engine.ollama_client import ollama_available
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
    use_llm = config.extract.use_llm and ollama_available(config.models.ollama_host)
    llm_fn = None if use_llm else (lambda *_args, **_kwargs: None)

    counts_in = 0
    counts_out = 0
    errors = 0
    skipped_version = 0
    unknown_only = 0
    export_rows: list[dict] = []

    rows = list(iter_relevant_documents(conn, sources))
    if not rows:
        report = {
            "extract_version": config.extract.version,
            "message": "no relevant documents; run --phase filter first",
            "counts_in": 0,
            "counts_out": 0,
        }
        return 0, 0, 0, json.dumps(report)

    for row in rows:
        counts_in += 1
        existing = get_enrichment(conn, row["doc_id"])
        if (
            config.extract.skip_if_same_version
            and existing is not None
            and existing["extract_version"] == config.extract.version
        ):
            skipped_version += 1
            counts_out += 1
            continue
        try:
            claim = extract_claim(
                doc_id=row["doc_id"],
                text=row["text"] or "",
                config=config,
                source=row["source"] or "",
                category=row["product_or_category"] or "",
                llm_fn=llm_fn,
            )
        except Exception:
            errors += 1
            continue
        if claim.jobs == ["unknown"] and not claim.blockers:
            unknown_only += 1
        upsert_enrichment_extract(
            conn,
            doc_id=row["doc_id"],
            claims=[claim.as_dict()],
            jobs=claim.jobs,
            blockers=claim.blockers,
            postponement_beyond_30d=claim.postponement_beyond_30d,
            outside_myntra_info_seeking=claim.outside_myntra_info_seeking,
            segment_clues=claim.segment_clues,
            confidence=claim.confidence,
            evidence_span=claim.evidence_span,
            extract_version=config.extract.version,
        )
        counts_out += 1
        export_rows.append(
            {
                "doc_id": claim.doc_id,
                "source": row["source"],
                "jobs": ",".join(claim.jobs),
                "blockers": ",".join(claim.blockers),
                "postponement_beyond_30d": claim.postponement_beyond_30d,
                "quote": claim.evidence_span,
            }
        )

    conn.commit()
    _write_export(config.extract.export_path, export_rows)
    gold = evaluate_extract_gold(config, llm_fn=llm_fn)
    report = {
        "extract_version": config.extract.version,
        "llm_used": use_llm,
        "counts_in": counts_in,
        "counts_out": counts_out,
        "unknown_only": unknown_only,
        "skipped_same_version": skipped_version,
        "error_count": errors,
        "export": str(config.extract.export_path),
        "gold": gold,
    }
    return counts_in, counts_out, errors, json.dumps(report)


def _write_export(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    csv_path = path.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["doc_id", "source", "jobs", "blockers", "postponement_beyond_30d", "quote"],
        )
        writer.writeheader()
        writer.writerows(rows)
