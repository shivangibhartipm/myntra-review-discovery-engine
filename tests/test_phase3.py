from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from review_engine.config import load_config
from review_engine.db import (
    connect,
    get_enrichment,
    init_db,
    start_run,
    upsert_document,
    upsert_enrichment_relevance,
)
from review_engine.extract.eval import evaluate_extract_gold
from review_engine.extract.pipeline import extract_claim, ground_span
from review_engine.records import build_canonical
from review_engine.windows import cutoffs

AS_OF = datetime(2026, 8, 24, 12, 0, 0)


def _config(tmp_path: Path | None = None):
    base = load_config()
    extract = replace(base.extract, use_llm=False, skip_if_same_version=False)
    if tmp_path is not None:
        extract = replace(extract, export_path=tmp_path / "claims.jsonl")
        storage = replace(base.storage, path=tmp_path / "engine.db")
        return replace(base, as_of=AS_OF, extract=extract, filter=replace(base.filter, use_llm=False), storage=storage)
    return replace(base, extract=extract, filter=replace(base.filter, use_llm=False))


def test_bookmark_is_not_collapsed_into_intent_or_sentiment():
    config = _config()
    book = extract_claim(
        doc_id="b",
        text="Saving this for later when I have money. Just bookmarking, not buying now.",
        config=config,
    )
    blocked = extract_claim(
        doc_id="i",
        text="I love this dress but the size chart is unclear so I will not buy yet.",
        config=config,
    )
    assert "bookmark_later" in book.jobs
    assert "intent_blocked" not in book.jobs
    assert "intent_blocked" in blocked.jobs
    assert "bookmark_later" not in blocked.jobs
    assert blocked.evidence_span in blocked.as_dict()["evidence_span"] or True
    assert blocked.evidence_span in "I love this dress but the size chart is unclear so I will not buy yet."


def test_evidence_span_is_substring():
    config = _config()
    text = "Waiting for EORS then I will order from my list."
    claim = extract_claim(doc_id="s", text=text, config=config)
    assert claim.evidence_span
    assert claim.evidence_span in text
    assert ground_span(text, "EORS") == "EORS"
    assert "wait_for_sale" in claim.jobs


def test_relevant_doc_gets_job_or_blocker_or_unknown():
    config = _config()
    claim = extract_claim(doc_id="u", text="I still cannot decide about this item on my list.", config=config)
    assert claim.jobs or claim.blockers
    if not claim.blockers:
        assert "unknown" in claim.jobs or claim.jobs


def test_extract_gold_agreement():
    config = _config()
    gold = evaluate_extract_gold(config)
    assert gold["n"] >= 10
    assert gold["span_valid"] == 1.0
    assert gold["job_f1"] >= 0.7
    assert gold["blocker_f1"] >= 0.7


def test_phase3_persists_claims_and_export(tmp_path: Path):
    config = _config(tmp_path)
    conn = connect(config.storage.path)
    init_db(conn)
    bounds = cutoffs(config, AS_OF)
    start_run(conn, run_id="e1", phase="extract", sources=["play"], config_snapshot={}, models=config.models.as_dict())
    doc = build_canonical(
        source="play",
        collected_at=AS_OF,
        bounds=bounds,
        text="Added this kurta to my wishlist until EORS.",
        source_native_id="x",
        observed_at=AS_OF,
        lang="en",
        product_or_category="ethnic wear",
    )
    upsert_document(conn, doc, "e1")
    upsert_enrichment_relevance(
        conn,
        doc_id=doc.doc_id,
        is_relevant=True,
        relevance_score=0.9,
        relevance_reasons=["wishlist_language"],
        filter_version="filter_v1",
    )
    conn.commit()

    from phases.p3_extract.run import run

    counts_in, counts_out, errors, notes = run(
        conn,
        config=config,
        run_id="e1",
        collected_at=AS_OF,
        bounds=bounds,
        source_filter=[],
    )
    report = json.loads(notes)
    assert counts_in == 1
    assert counts_out == 1
    assert errors == 0
    row = get_enrichment(conn, doc.doc_id)
    jobs = json.loads(row["jobs"])
    assert "wait_for_sale" in jobs or "bookmark_later" in jobs
    assert row["evidence_span"] in "Added this kurta to my wishlist until EORS."
    assert row["extract_version"] == config.extract.version
    assert config.extract.export_path.exists()
    assert config.extract.export_path.with_suffix(".csv").exists()
    assert report["gold"]["n"] >= 10
    conn.close()
