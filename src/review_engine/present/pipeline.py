from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from review_engine.config import AppConfig
from review_engine.db import (
    count_documents,
    count_relevant_documents,
    counts_by_source_and_layer,
    fetch_documents_by_ids,
    fetch_documents_with_relevance,
    fetch_enrichments_by_ids,
    fetch_opportunity_areas,
    fetch_recent_runs,
    relevance_yield_by_source,
)
from review_engine.pii import contains_pii
from review_engine.present.briefing import build_briefing
from review_engine.present.normalize import board_row, maybe_json, row_to_dict
from review_engine.present.reports import onepager_markdown, ranked_markdown, write_csv
from review_engine.present.segments import demographic_segments_from_db
from review_engine.present.sources import EXCLUDED_BOARD_SOURCES
from review_engine.present.stuck_reasons import (
    stuck_reason_catalog,
)
from review_engine.present.wishlist_signals import analyze_wishlist_signals
from review_engine.windows import Cutoffs


def present_opportunities(
    conn,
    *,
    config: AppConfig,
    bounds: Cutoffs,
    collected_at: datetime,
) -> dict[str, Any]:
    raw_rows = _load_ranked(conn, config)
    member_ids: list[str] = []
    quote_ids: list[str] = []
    for row in raw_rows:
        member_ids.extend(str(x) for x in (row.get("member_doc_ids") or []))
        for quote in row.get("quotes") or []:
            if isinstance(quote, dict) and quote.get("doc_id"):
                quote_ids.append(str(quote["doc_id"]))
    docs = {k: dict(v) for k, v in fetch_documents_by_ids(conn, member_ids + quote_ids).items()}
    enrichments = {k: dict(v) for k, v in fetch_enrichments_by_ids(conn, member_ids + quote_ids).items()}
    opportunities = [board_row(row, documents=docs, enrichments=enrichments) for row in raw_rows]
    opportunities.sort(key=lambda o: (o.get("rank_90d") is None, o.get("rank_90d") or 10**9))

    health = corpus_health(conn, bounds=bounds, collected_at=collected_at)
    health = _strip_excluded_sources(health)
    message = None if opportunities else "No ranked opportunities. Run `--phase rank` first."
    demo = demographic_segments_from_db(config.storage.path)
    doc_rows = [dict(r) for r in fetch_documents_with_relevance(conn)]
    wishlist_signals = analyze_wishlist_signals(doc_rows)
    stuck_catalog = stuck_reason_catalog(doc_rows, relevant_only=True)
    health["stuck_reason_catalog"] = stuck_catalog
    briefing = build_briefing(
        opportunities, demographic_segments=demo, wishlist_signals=wishlist_signals
    )

    payload = {
        "generated_at": collected_at.isoformat(timespec="seconds"),
        "present_version": config.present.version,
        "headline": "Wishlist → purchase: within 30 days and overall",
        "windows": bounds.as_dict(),
        "corpus_health": health,
        "message": message,
        "briefing": briefing,
        "opportunities": opportunities,
    }

    cfg = config.present
    _write_json(cfg.export_path, payload)
    _write_json(cfg.export_path.parent / "corpus_health.json", health)
    _write_quotes(cfg.quotes_dir, opportunities)
    _write_audit(cfg.audit_path, enrichments, docs, quote_ids)

    report_dir = cfg.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    md = ranked_markdown(
        opportunities,
        windows=bounds.as_dict(),
        corpus_health=health,
        message=message,
        briefing=briefing,
    )
    (report_dir / "ranked.md").write_text(md, encoding="utf-8")
    write_csv(report_dir / "opportunities.csv", opportunities)
    onepager_dir = report_dir / "onepagers"
    if onepager_dir.exists():
        shutil.rmtree(onepager_dir)
    onepager_dir.mkdir(parents=True, exist_ok=True)
    for row in opportunities[: cfg.top_n_onepagers]:
        name = str(row.get("opportunity_id") or "opportunity")
        (onepager_dir / f"{name}.md").write_text(onepager_markdown(row), encoding="utf-8")

    leaked = _scan_quote_pii(opportunities)
    if leaked:
        raise ValueError(f"PII leaked in present quotes: {leaked[:8]}")

    _copy_web_data(cfg)
    n_in = len(raw_rows)
    n_out = len(opportunities)
    top_id = opportunities[0]["opportunity_id"] if opportunities else None
    return {
        "present_version": config.present.version,
        "counts_in": n_in,
        "counts_out": n_out,
        "message": message,
        "export": str(cfg.export_path),
        "report": str(report_dir / "ranked.md"),
        "csv": str(report_dir / "opportunities.csv"),
        "quotes_dir": str(cfg.quotes_dir),
        "web_data_dir": str(cfg.web_data_dir),
        "top_opportunity_id": top_id,
    }


def corpus_health(conn, *, bounds: Cutoffs, collected_at: datetime) -> dict[str, Any]:
    runs = [dict(r) for r in fetch_recent_runs(conn, 12)]
    last = runs[0] if runs else {}
    return {
        "n_unfiltered": count_documents(conn),
        "n_relevant": count_relevant_documents(conn),
        "yield_by_source": relevance_yield_by_source(conn),
        "counts": counts_by_source_and_layer(conn),
        "windows": bounds.as_dict(),
        "collected_at": collected_at.isoformat(timespec="seconds"),
        "last_run": {
            "run_id": last.get("run_id"),
            "phase": last.get("phase"),
            "started_at": last.get("started_at"),
            "finished_at": last.get("finished_at"),
            "counts_in": last.get("counts_in"),
            "counts_out": last.get("counts_out"),
        }
        if last
        else {},
        "recent_runs": [
            {
                "run_id": r.get("run_id"),
                "phase": r.get("phase"),
                "started_at": r.get("started_at"),
                "counts_in": r.get("counts_in"),
                "counts_out": r.get("counts_out"),
                "error_count": r.get("error_count"),
            }
            for r in runs
        ],
    }


def _load_ranked(conn, config: AppConfig) -> list[dict[str, Any]]:
    db_rows = [row_to_dict(row) for row in fetch_opportunity_areas(conn)]
    ranked = [r for r in db_rows if r.get("rank_90d") is not None]
    if ranked:
        return ranked
    path = config.present.ranked_path
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [row_to_dict(item) for item in data]
        if isinstance(data, dict) and isinstance(data.get("opportunities"), list):
            return [row_to_dict(item) for item in data["opportunities"]]
    return []


def _strip_excluded_sources(health: dict[str, Any]) -> dict[str, Any]:
    out = dict(health)
    excluded = set(EXCLUDED_BOARD_SOURCES)

    yield_by_source = {
        k: v for k, v in dict(out.get("yield_by_source") or {}).items() if k not in excluded
    }
    out["yield_by_source"] = yield_by_source

    counts = dict(out.get("counts") or {})
    by_source = {k: v for k, v in dict(counts.get("by_source") or {}).items() if k not in excluded}
    by_source_layer = {
        k: v for k, v in dict(counts.get("by_source_layer") or {}).items() if k not in excluded
    }
    counts["by_source"] = by_source
    counts["by_source_layer"] = by_source_layer
    out["counts"] = counts

    out["n_unfiltered"] = int(sum(by_source.values()))
    out["n_relevant"] = int(
        sum(int(v.get("relevant") or 0) for v in yield_by_source.values())
    )
    return out


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _write_quotes(quotes_dir: Path, opportunities: list[dict[str, Any]]) -> None:
    if quotes_dir.exists():
        shutil.rmtree(quotes_dir)
    quotes_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for opp in opportunities:
        for quote in opp.get("quotes") or []:
            doc_id = str(quote.get("doc_id") or "")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            _write_json(quotes_dir / f"{doc_id}.json", {**quote, "opportunity_id": opp.get("opportunity_id")})


def _write_audit(
    path: Path,
    enrichments: dict[str, dict[str, Any]],
    docs: dict[str, dict[str, Any]],
    quote_ids: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for doc_id in dict.fromkeys(quote_ids):
            enr = enrichments.get(doc_id) or {}
            doc = docs.get(doc_id) or {}
            record = {
                "doc_id": doc_id,
                "source": doc.get("source"),
                "observed_at": doc.get("observed_at"),
                "jobs": maybe_json(enr.get("jobs")),
                "blockers": maybe_json(enr.get("blockers")),
                "evidence_span": enr.get("evidence_span"),
                "postponement_beyond_30d": enr.get("postponement_beyond_30d"),
            }
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _scan_quote_pii(opportunities: list[dict[str, Any]]) -> list[str]:
    leaked: list[str] = []
    for opp in opportunities:
        for field in ("problem_one_liner", "delay_mechanism", "comparison_notes", "suggested_lever"):
            if contains_pii(str(opp.get(field) or "")):
                leaked.append(str(opp.get("opportunity_id")))
        for quote in opp.get("quotes") or []:
            if contains_pii(str(quote.get("quote") or "")):
                leaked.append(str(quote.get("doc_id") or opp.get("opportunity_id")))
    return leaked


def _copy_web_data(cfg) -> None:
    dest = cfg.web_data_dir
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cfg.export_path, dest / "opportunities.json")
    health = cfg.export_path.parent / "corpus_health.json"
    if health.exists():
        shutil.copy2(health, dest / "corpus_health.json")
    quotes_dest = dest / "quotes"
    if quotes_dest.exists():
        shutil.rmtree(quotes_dest)
    if cfg.quotes_dir.exists():
        shutil.copytree(cfg.quotes_dir, quotes_dest)
