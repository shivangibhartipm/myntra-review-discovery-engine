from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from review_engine.config import load_config
from review_engine.db import connect, get_enrichment, init_db, start_run, upsert_document
from review_engine.eval_gold import evaluate_gold
from review_engine.records import build_canonical
from review_engine.relevance.lexical import lexical_gate
from review_engine.relevance.pipeline import classify_text
from review_engine.windows import cutoffs

AS_OF = datetime(2026, 8, 24, 12, 0, 0)


def _config(tmp_path: Path):
    base = load_config()
    filt = replace(base.filter, use_llm=False, skip_if_same_version=False, sample_path=tmp_path / "sample.json")
    return replace(base, as_of=AS_OF, filter=filt, storage=replace(base.storage, path=tmp_path / "engine.db"))


def test_lexical_keeps_sale_wait_without_wishlist_word():
    result = lexical_gate("Waiting for EORS then I will order.")
    assert result.gated
    assert "price_wait" in result.tags


def test_otp_and_crash_are_not_relevant():
    config = load_config()
    config = replace(config, filter=replace(config.filter, use_llm=False))
    otp = classify_text("OTP not coming. Cannot even login to the app.", config)
    crash = classify_text("App crashed during sale event, unusable, one star.", config)
    assert otp.is_relevant is False
    assert crash.is_relevant is False


def test_compare_and_wishlist_are_relevant():
    config = load_config()
    config = replace(config, filter=replace(config.filter, use_llm=False))
    wish = classify_text("Added this kurta to my wishlist until EORS.", config)
    compare = classify_text("Confused between two kurtas, which is better?", config)
    assert wish.is_relevant
    assert "wishlist_language" in wish.relevance_reasons
    assert compare.is_relevant
    assert "compare" in compare.relevance_reasons


def test_gold_precision_recall_heuristic():
    config = load_config()
    config = replace(config, filter=replace(config.filter, use_llm=False))
    gold = evaluate_gold(config)
    assert gold["n"] >= 20
    assert gold["precision"] >= 0.7
    assert gold["recall"] >= 0.7


def test_phase2_writes_enrichment_and_yield(tmp_path: Path):
    config = _config(tmp_path)
    conn = connect(config.storage.path)
    init_db(conn)
    bounds = cutoffs(config, AS_OF)
    start_run(
        conn,
        run_id="f1",
        phase="filter",
        sources=["play"],
        config_snapshot={},
        models=config.models.as_dict(),
    )
    docs = [
        build_canonical(
            source="play",
            collected_at=AS_OF,
            bounds=bounds,
            text="Added to wishlist until sale.",
            source_native_id="a",
            observed_at=AS_OF,
            lang="en",
        ),
        build_canonical(
            source="play",
            collected_at=AS_OF,
            bounds=bounds,
            text="OTP not received, cannot login.",
            source_native_id="b",
            observed_at=AS_OF,
            lang="en",
        ),
        build_canonical(
            source="reddit",
            collected_at=AS_OF,
            bounds=bounds,
            text="Myntra or Ajio for these two dresses?",
            source_native_id="c",
            observed_at=AS_OF,
            lang="en",
        ),
    ]
    for doc in docs:
        upsert_document(conn, doc, "f1")
    conn.commit()

    from phases.p2_filter.run import run

    counts_in, counts_out, errors, notes = run(
        conn,
        config=config,
        run_id="f1",
        collected_at=AS_OF,
        bounds=bounds,
        source_filter=[],
    )
    report = json.loads(notes)
    assert counts_in == 3
    assert counts_out == 2
    assert errors == 0
    assert report["yield_by_source"]["play"]["unfiltered"] == 2
    assert report["yield_by_source"]["play"]["relevant"] == 1
    assert report["gold"]["n"] >= 20
    wish = conn.execute("SELECT doc_id FROM raw_documents WHERE source_native_id='a'").fetchone()
    row = get_enrichment(conn, wish["doc_id"])
    assert row["is_relevant"] == 1
    assert row["filter_version"] == config.filter.version
    conn.close()
