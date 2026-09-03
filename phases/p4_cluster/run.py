"""Phase 4 — Cluster claims into named opportunity areas."""

from __future__ import annotations

import json
from datetime import datetime

from review_engine.cluster.pipeline import build_member, cluster_members, name_clusters, vector_for_row
from review_engine.config import AppConfig
from review_engine.db import (
    fetch_opportunity_areas,
    iter_extracted_documents,
    replace_opportunity_areas,
    upsert_enrichment_cluster,
)
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
    del collected_at, bounds
    sources = source_filter or None
    rows = list(iter_extracted_documents(conn, sources))
    if not rows:
        report = {
            "cluster_version": config.cluster.version,
            "message": "no extracted documents; run --phase extract first",
            "counts_in": 0,
            "counts_out": 0,
        }
        return 0, 0, 0, json.dumps(report)

    if config.cluster.skip_if_same_version and _already_clustered(rows, config.cluster.version):
        existing = fetch_opportunity_areas(conn)
        report = {
            "cluster_version": config.cluster.version,
            "skipped_same_version": True,
            "counts_in": len(rows),
            "counts_out": len(existing),
            "opportunities": [row["opportunity_id"] for row in existing],
        }
        return len(rows), len(existing), 0, json.dumps(report)

    use_dense = config.cluster.use_embed and ollama_available(config.models.ollama_host)
    use_llm = config.cluster.use_llm and ollama_available(config.models.ollama_host)

    members = []
    errors = 0
    embeddings: dict[str, list[float]] = {}
    for row in rows:
        try:
            vec = vector_for_row(row, config=config, use_dense=use_dense)
            members.append(build_member(row, vec))
            embeddings[row["doc_id"]] = vec
        except Exception:
            errors += 1

    clusters = cluster_members(
        members,
        min_k=config.cluster.min_opportunities,
        max_k=config.cluster.max_opportunities,
        min_size=config.cluster.min_cluster_size,
        merge_cosine=config.cluster.merge_cosine,
    )
    opportunities = name_clusters(clusters, config=config, use_llm=use_llm)
    assignment = {doc_id: opp.opportunity_id for opp in opportunities for doc_id in opp.member_doc_ids}

    for row in rows:
        upsert_enrichment_cluster(
            conn,
            doc_id=row["doc_id"],
            embedding=embeddings.get(row["doc_id"]),
            cluster_id=assignment.get(row["doc_id"]),
            cluster_version=config.cluster.version,
        )
    replace_opportunity_areas(conn, run_id, [o.as_dict() for o in opportunities])
    conn.commit()
    _write_export(config.cluster.export_path, [o.as_dict() for o in opportunities])

    names = [o.problem_one_liner for o in opportunities]
    report = {
        "cluster_version": config.cluster.version,
        "embed_used": use_dense,
        "llm_used": use_llm,
        "counts_in": len(rows),
        "counts_out": len(opportunities),
        "error_count": errors,
        "single_source_warnings": sum(1 for o in opportunities if o.single_source_warning),
        "opportunity_ids": [o.opportunity_id for o in opportunities],
        "problem_one_liners": names,
        "export": str(config.cluster.export_path),
        "distinct_names": len(set(names)),
    }
    return len(rows), len(opportunities), errors, json.dumps(report)


def _already_clustered(rows, version: str) -> bool:
    if not rows:
        return False
    return all(row["cluster_version"] == version and row["cluster_id"] for row in rows)


def _write_export(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
