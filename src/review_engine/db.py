from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from review_engine.records import CanonicalDocument

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate_schema(conn)
    conn.commit()


def _migrate_schema(conn: sqlite3.Connection) -> None:
    _add_column(conn, "document_enrichment", "cluster_version", "TEXT")
    _add_column(conn, "opportunity_areas", "cluster_version", "TEXT")
    _add_column(conn, "opportunity_areas", "single_source_warning", "INTEGER")
    _add_column(conn, "opportunity_areas", "quotes", "TEXT")
    _add_column(conn, "opportunity_areas", "naming_source", "TEXT")
    _add_column(conn, "opportunity_areas", "rank_score_90d", "REAL")
    _add_column(conn, "opportunity_areas", "rank_score_12m", "REAL")
    _add_column(conn, "opportunity_areas", "volume_rank", "INTEGER")
    _add_column(conn, "opportunity_areas", "multi_source_support", "REAL")
    _add_column(conn, "opportunity_areas", "intent_vs_bookmark", "TEXT")
    _add_column(conn, "opportunity_areas", "delay_mechanism", "TEXT")
    _add_column(conn, "opportunity_areas", "segment_slices", "TEXT")
    _add_column(conn, "opportunity_areas", "rank_version", "TEXT")


def _add_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {row["name"] for row in rows}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def start_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    phase: str,
    sources: Iterable[str],
    config_snapshot: dict[str, Any],
    models: dict[str, str],
) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_id, started_at, phase, sources, config_snapshot, models)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            utcnow().isoformat(timespec="seconds"),
            phase,
            json.dumps(list(sources)),
            json.dumps(config_snapshot, default=str),
            json.dumps(models),
        ),
    )
    conn.commit()


def finish_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    counts_in: int,
    counts_out: int,
    error_count: int,
    notes: str | None = None,
) -> None:
    error_rate = (error_count / counts_in) if counts_in else 0.0
    conn.execute(
        """
        UPDATE runs
        SET finished_at = ?, counts_in = ?, counts_out = ?, error_count = ?, error_rate = ?, notes = ?
        WHERE run_id = ?
        """,
        (
            utcnow().isoformat(timespec="seconds"),
            counts_in,
            counts_out,
            error_count,
            error_rate,
            notes,
            run_id,
        ),
    )
    conn.commit()


def upsert_document(conn: sqlite3.Connection, doc: CanonicalDocument, run_id: str) -> None:
    row = doc.to_row()
    conn.execute(
        """
        INSERT INTO raw_documents (
            doc_id, source, source_native_id, url, observed_at, collected_at,
            text, lang, rating, thread_id, product_or_category, corpus_layer, run_id
        ) VALUES (
            :doc_id, :source, :source_native_id, :url, :observed_at, :collected_at,
            :text, :lang, :rating, :thread_id, :product_or_category, :corpus_layer, :run_id
        )
        ON CONFLICT(doc_id) DO UPDATE SET
            text = excluded.text,
            lang = excluded.lang,
            rating = excluded.rating,
            corpus_layer = excluded.corpus_layer,
            run_id = excluded.run_id
        """,
        {**row, "run_id": run_id},
    )


def upsert_checkpoint(
    conn: sqlite3.Connection,
    source: str,
    cursor: str | None,
    last_observed_at: datetime | None,
) -> None:
    conn.execute(
        """
        INSERT INTO collector_checkpoints (source, cursor, last_observed_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
            cursor = excluded.cursor,
            last_observed_at = excluded.last_observed_at,
            updated_at = excluded.updated_at
        """,
        (
            source,
            cursor,
            last_observed_at.isoformat(timespec="seconds") if last_observed_at else None,
            utcnow().isoformat(timespec="seconds"),
        ),
    )


def get_checkpoint(conn: sqlite3.Connection, source: str) -> tuple[str | None, datetime | None]:
    row = conn.execute(
        "SELECT cursor, last_observed_at FROM collector_checkpoints WHERE source = ?",
        (source,),
    ).fetchone()
    if not row:
        return None, None
    last = None
    if row["last_observed_at"]:
        last = datetime.fromisoformat(row["last_observed_at"])
    return row["cursor"], last


def document_exists(conn: sqlite3.Connection, doc_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM raw_documents WHERE doc_id = ?", (doc_id,)).fetchone()
    return row is not None


def counts_by_source_and_layer(conn: sqlite3.Connection) -> dict[str, Any]:
    by_source: dict[str, int] = {}
    by_layer: dict[str, int] = {}
    by_source_layer: dict[str, dict[str, int]] = {}
    rows = conn.execute(
        """
        SELECT source, corpus_layer, COUNT(*) AS n
        FROM raw_documents
        GROUP BY source, corpus_layer
        """
    )
    for row in rows:
        source = row["source"]
        layer = row["corpus_layer"] or "unspecified"
        n = int(row["n"])
        by_source[source] = by_source.get(source, 0) + n
        by_layer[layer] = by_layer.get(layer, 0) + n
        by_source_layer.setdefault(source, {})[layer] = n
    return {"by_source": by_source, "by_layer": by_layer, "by_source_layer": by_source_layer}


def fetch_run(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()


def count_documents(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM raw_documents").fetchone()
    return int(row["n"])


def count_relevant_documents(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM document_enrichment WHERE is_relevant = 1"
    ).fetchone()
    return int(row["n"])


def fetch_documents_with_relevance(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT d.text, d.source, COALESCE(e.is_relevant, 0) AS is_relevant
        FROM raw_documents d
        LEFT JOIN document_enrichment e ON e.doc_id = d.doc_id
        WHERE d.source NOT IN ('stub')
        ORDER BY d.observed_at DESC
        """
    ).fetchall()


def iter_raw_documents(conn: sqlite3.Connection, sources: list[str] | None = None):
    if sources:
        placeholders = ",".join("?" * len(sources))
        sql = f"SELECT * FROM raw_documents WHERE source IN ({placeholders}) ORDER BY observed_at DESC"
        return conn.execute(sql, sources)
    return conn.execute("SELECT * FROM raw_documents ORDER BY observed_at DESC")


def get_enrichment(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM document_enrichment WHERE doc_id = ?", (doc_id,)).fetchone()


def upsert_enrichment_relevance(
    conn: sqlite3.Connection,
    *,
    doc_id: str,
    is_relevant: bool,
    relevance_score: float,
    relevance_reasons: list[str] | tuple[str, ...],
    filter_version: str,
) -> None:
    conn.execute(
        """
        INSERT INTO document_enrichment (
            doc_id, is_relevant, relevance_score, relevance_reasons, filter_version, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
            is_relevant = excluded.is_relevant,
            relevance_score = excluded.relevance_score,
            relevance_reasons = excluded.relevance_reasons,
            filter_version = excluded.filter_version,
            updated_at = excluded.updated_at
        """,
        (
            doc_id,
            1 if is_relevant else 0,
            relevance_score,
            json.dumps(list(relevance_reasons)),
            filter_version,
            utcnow().isoformat(timespec="seconds"),
        ),
    )


def relevance_yield_by_source(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT d.source,
               COUNT(*) AS unfiltered,
               SUM(CASE WHEN e.doc_id IS NOT NULL THEN 1 ELSE 0 END) AS scored,
               SUM(CASE WHEN e.is_relevant = 1 THEN 1 ELSE 0 END) AS relevant
        FROM raw_documents d
        LEFT JOIN document_enrichment e ON e.doc_id = d.doc_id
        GROUP BY d.source
        """
    )
    out: dict[str, Any] = {}
    for row in rows:
        unfiltered = int(row["unfiltered"])
        relevant = int(row["relevant"] or 0)
        out[row["source"]] = {
            "unfiltered": unfiltered,
            "scored": int(row["scored"] or 0),
            "relevant": relevant,
            "yield": round(relevant / unfiltered, 4) if unfiltered else 0.0,
        }
    return out


def iter_relevant_documents(conn: sqlite3.Connection, sources: list[str] | None = None):
    sql = """
        SELECT d.*, e.is_relevant, e.filter_version, e.extract_version
        FROM raw_documents d
        INNER JOIN document_enrichment e ON e.doc_id = d.doc_id
        WHERE e.is_relevant = 1
    """
    params: list[Any] = []
    if sources:
        placeholders = ",".join("?" * len(sources))
        sql += f" AND d.source IN ({placeholders})"
        params.extend(sources)
    sql += " ORDER BY d.observed_at DESC"
    return conn.execute(sql, params)


def upsert_enrichment_extract(
    conn: sqlite3.Connection,
    *,
    doc_id: str,
    claims: list[dict[str, Any]],
    jobs: list[str],
    blockers: list[str],
    postponement_beyond_30d: str,
    outside_myntra_info_seeking: bool,
    segment_clues: list[str],
    confidence: float,
    evidence_span: str,
    extract_version: str,
) -> None:
    payload = (
        json.dumps(claims),
        json.dumps(jobs),
        json.dumps(blockers),
        postponement_beyond_30d,
        1 if outside_myntra_info_seeking else 0,
        json.dumps(segment_clues),
        confidence,
        evidence_span,
        extract_version,
        utcnow().isoformat(timespec="seconds"),
        doc_id,
    )
    cur = conn.execute(
        """
        UPDATE document_enrichment SET
            claims = ?, jobs = ?, blockers = ?, postponement_beyond_30d = ?,
            outside_myntra_info_seeking = ?, segment_clues = ?, confidence = ?,
            evidence_span = ?, extract_version = ?, updated_at = ?
        WHERE doc_id = ?
        """,
        payload,
    )
    if cur.rowcount == 0:
        conn.execute(
            """
            INSERT INTO document_enrichment (
                doc_id, is_relevant, claims, jobs, blockers, postponement_beyond_30d,
                outside_myntra_info_seeking, segment_clues, confidence, evidence_span,
                extract_version, updated_at
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, *payload[:-1]),
        )


def iter_extracted_documents(conn: sqlite3.Connection, sources: list[str] | None = None):
    sql = """
        SELECT d.*, e.jobs, e.blockers, e.evidence_span, e.claims, e.extract_version,
               e.embedding, e.cluster_id, e.cluster_version, e.postponement_beyond_30d,
               e.segment_clues
        FROM raw_documents d
        INNER JOIN document_enrichment e ON e.doc_id = d.doc_id
        WHERE e.is_relevant = 1 AND e.extract_version IS NOT NULL
    """
    params: list[Any] = []
    if sources:
        placeholders = ",".join("?" * len(sources))
        sql += f" AND d.source IN ({placeholders})"
        params.extend(sources)
    sql += " ORDER BY d.observed_at DESC"
    return conn.execute(sql, params)


def upsert_enrichment_cluster(
    conn: sqlite3.Connection,
    *,
    doc_id: str,
    embedding: list[float] | None,
    cluster_id: str | None,
    cluster_version: str,
) -> None:
    conn.execute(
        """
        UPDATE document_enrichment
        SET embedding = ?, cluster_id = ?, cluster_version = ?, updated_at = ?
        WHERE doc_id = ?
        """,
        (
            json.dumps(embedding) if embedding is not None else None,
            cluster_id,
            cluster_version,
            utcnow().isoformat(timespec="seconds"),
            doc_id,
        ),
    )


def replace_opportunity_areas(
    conn: sqlite3.Connection,
    run_id: str,
    rows: list[dict[str, Any]],
) -> None:
    conn.execute("DELETE FROM opportunity_areas")
    for row in rows:
        conn.execute(
            """
            INSERT INTO opportunity_areas (
                opportunity_id, run_id, cluster_version, problem_one_liner,
                member_doc_ids, representative_doc_ids, job_mix, blocker_mix,
                source_mix, single_source_warning, quotes, naming_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["opportunity_id"],
                run_id,
                row.get("cluster_version"),
                row["problem_one_liner"],
                json.dumps(row["member_doc_ids"]),
                json.dumps(row["representative_doc_ids"]),
                json.dumps(row["job_mix"]),
                json.dumps(row["blocker_mix"]),
                json.dumps(row["source_mix"]),
                1 if row.get("single_source_warning") else 0,
                json.dumps(row.get("quotes") or []),
                row.get("naming_source"),
            ),
        )


def fetch_opportunity_areas(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM opportunity_areas ORDER BY opportunity_id"))


def apply_opportunity_ranks(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        conn.execute(
            """
            UPDATE opportunity_areas SET
                rank_score = ?,
                rank_score_90d = ?,
                rank_score_12m = ?,
                rank_90d = ?,
                rank_12m = ?,
                volume_rank = ?,
                prevalence_relevant = ?,
                prevalence_unfiltered = ?,
                recency_90d_share = ?,
                postponement_rate = ?,
                metric_relevance = ?,
                actionability = ?,
                multi_source_support = ?,
                intent_vs_bookmark = ?,
                delay_mechanism = ?,
                segment_slices = ?,
                comparison_notes = ?,
                rank_version = ?
            WHERE opportunity_id = ?
            """,
            (
                row.get("rank_score"),
                row.get("rank_score_90d"),
                row.get("rank_score_12m"),
                row.get("rank_90d"),
                row.get("rank_12m"),
                row.get("volume_rank"),
                row.get("prevalence_relevant"),
                row.get("prevalence_unfiltered"),
                row.get("recency_90d_share"),
                row.get("postponement_rate"),
                row.get("metric_relevance"),
                row.get("actionability"),
                row.get("multi_source_support"),
                json.dumps(row.get("intent_vs_bookmark") or {}),
                row.get("delay_mechanism"),
                json.dumps(row.get("segment_slices") or []),
                row.get("comparison_notes"),
                row.get("rank_version"),
                row["opportunity_id"],
            ),
        )


def fetch_recent_runs(conn: sqlite3.Connection, limit: int = 12) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
    )


def fetch_documents_by_ids(conn: sqlite3.Connection, doc_ids: Iterable[str]) -> dict[str, sqlite3.Row]:
    ids = [d for d in doc_ids if d]
    out: dict[str, sqlite3.Row] = {}
    for i in range(0, len(ids), 400):
        chunk = ids[i : i + 400]
        placeholders = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT * FROM raw_documents WHERE doc_id IN ({placeholders})",
            chunk,
        )
        for row in rows:
            out[row["doc_id"]] = row
    return out


def fetch_enrichments_by_ids(conn: sqlite3.Connection, doc_ids: Iterable[str]) -> dict[str, sqlite3.Row]:
    ids = [d for d in doc_ids if d]
    out: dict[str, sqlite3.Row] = {}
    for i in range(0, len(ids), 400):
        chunk = ids[i : i + 400]
        placeholders = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT * FROM document_enrichment WHERE doc_id IN ({placeholders})",
            chunk,
        )
        for row in rows:
            out[row["doc_id"]] = row
    return out

