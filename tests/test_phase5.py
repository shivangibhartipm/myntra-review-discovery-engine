from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from review_engine.config import load_config
from review_engine.db import (
    connect,
    fetch_opportunity_areas,
    init_db,
    start_run,
    upsert_document,
    upsert_enrichment_extract,
    upsert_enrichment_relevance,
    replace_opportunity_areas,
)
from review_engine.rank.pipeline import rank_opportunities, volume_order_differs
from review_engine.rank.rubrics import metric_relevance
from review_engine.records import build_canonical
from review_engine.windows import cutoffs

AS_OF = datetime(2026, 8, 24, 12, 0, 0)


def _config(tmp_path: Path):
    base = load_config()
    rank = replace(base.rank, export_path=tmp_path / "opportunities_ranked.json", min_segment_n=30)
    storage = replace(base.storage, path=tmp_path / "engine.db")
    return replace(
        base,
        as_of=AS_OF,
        rank=rank,
        cluster=replace(base.cluster, use_embed=False, use_llm=False),
        extract=replace(base.extract, use_llm=False),
        filter=replace(base.filter, use_llm=False),
        storage=storage,
    )


def _add_doc(
    conn,
    config,
    bounds,
    *,
    source: str,
    native: str,
    text: str,
    observed_at: datetime,
    relevant: bool,
    jobs: list[str] | None = None,
    blockers: list[str] | None = None,
    postpone: str = "unknown",
    clues: list[str] | None = None,
    rating: float | None = None,
):
    doc = build_canonical(
        source=source,
        collected_at=AS_OF,
        bounds=bounds,
        text=text,
        source_native_id=native,
        observed_at=observed_at,
        lang="en",
        rating=rating,
    )
    upsert_document(conn, doc, "r1")
    upsert_enrichment_relevance(
        conn,
        doc_id=doc.doc_id,
        is_relevant=relevant,
        relevance_score=0.9 if relevant else 0.1,
        relevance_reasons=["wishlist_language"] if relevant else ["delivery_complaint"],
        filter_version="filter_v1",
    )
    if relevant:
        upsert_enrichment_extract(
            conn,
            doc_id=doc.doc_id,
            claims=[{"doc_id": doc.doc_id, "jobs": jobs or [], "blockers": blockers or []}],
            jobs=jobs or [],
            blockers=blockers or [],
            postponement_beyond_30d=postpone,
            outside_myntra_info_seeking=source in {"reddit", "youtube"},
            segment_clues=clues or [],
            confidence=0.8,
            evidence_span=text[:40],
            extract_version=config.extract.version,
        )
    return doc.doc_id


def _seed_sale_vs_delivery(conn, config):
    bounds = cutoffs(config, AS_OF)
    start_run(
        conn,
        run_id="r1",
        phase="rank",
        sources=["play"],
        config_snapshot={},
        models=config.models.as_dict(),
    )
    recent = datetime(2026, 8, 1)
    sale_ids = []
    for i, source in enumerate(["play", "reddit", "youtube"]):
        sale_ids.append(
            _add_doc(
                conn,
                config,
                bounds,
                source=source,
                native=f"sale{i}",
                text="Added to wishlist until EORS / waiting for the sale to buy.",
                observed_at=recent,
                relevant=True,
                jobs=["wait_for_sale"],
                blockers=["sale_timing"],
                postpone="yes",
            )
        )
    delivery_ids = []
    for i in range(12):
        delivery_ids.append(
            _add_doc(
                conn,
                config,
                bounds,
                source="play",
                native=f"del{i}",
                text="Delivery is late and the app is terrible. 1 star.",
                observed_at=recent,
                relevant=True,
                jobs=["unknown"],
                blockers=["delivery_checkout_saved"],
                postpone="unknown",
                rating=1.0,
            )
        )
    for i in range(40):
        _add_doc(
            conn,
            config,
            bounds,
            source="play",
            native=f"noise{i}",
            text="Package delayed courier not reachable. Worst delivery.",
            observed_at=recent,
            relevant=False,
            rating=1.0,
        )
    replace_opportunity_areas(
        conn,
        "r1",
        [
            {
                "opportunity_id": "wait_for_sale_sale_timing",
                "cluster_version": "cluster_v1",
                "problem_one_liner": "Users wait for a sale before buying saved items.",
                "member_doc_ids": sale_ids,
                "representative_doc_ids": sale_ids[:2],
                "job_mix": {"wait_for_sale": 1.0},
                "blocker_mix": {"sale_timing": 1.0},
                "source_mix": {"play": 0.33, "reddit": 0.33, "youtube": 0.34},
                "single_source_warning": False,
                "quotes": [{"doc_id": sale_ids[0], "quote": "waiting for the sale", "source": "play"}],
                "naming_source": "template",
            },
            {
                "opportunity_id": "unknown_delivery_checkout_saved",
                "cluster_version": "cluster_v1",
                "problem_one_liner": "Users hesitate on a saved item because checkout or delivery fails.",
                "member_doc_ids": delivery_ids,
                "representative_doc_ids": delivery_ids[:2],
                "job_mix": {"unknown": 1.0},
                "blocker_mix": {"delivery_checkout_saved": 1.0},
                "source_mix": {"play": 1.0},
                "single_source_warning": True,
                "quotes": [{"doc_id": delivery_ids[0], "quote": "Delivery is late", "source": "play"}],
                "naming_source": "template",
            },
        ],
    )
    conn.commit()
    return bounds, sale_ids, delivery_ids


def test_sale_wait_outranks_loud_delivery_on_metric_not_volume():
    assert metric_relevance({"wait_for_sale": 1.0}, {"sale_timing": 1.0}) == 5
    assert metric_relevance({"unknown": 1.0}, {"delivery_checkout_saved": 1.0}) == 2


def test_phase5_rank_order_differs_from_volume(tmp_path: Path):
    config = _config(tmp_path)
    conn = connect(config.storage.path)
    init_db(conn)
    bounds, _, _ = _seed_sale_vs_delivery(conn, config)

    from phases.p5_rank.run import run

    counts_in, counts_out, errors, notes = run(
        conn,
        config=config,
        run_id="r1",
        collected_at=AS_OF,
        bounds=bounds,
        source_filter=[],
    )
    report = json.loads(notes)
    assert errors == 0
    assert counts_in == 2
    assert counts_out == 2
    assert report["volume_order_differs"] is True

    rows = {row["opportunity_id"]: row for row in fetch_opportunity_areas(conn)}
    sale = rows["wait_for_sale_sale_timing"]
    delivery = rows["unknown_delivery_checkout_saved"]
    assert sale["rank_90d"] == 1
    assert delivery["rank_90d"] == 2
    assert delivery["volume_rank"] == 1
    assert sale["volume_rank"] == 2
    assert sale["metric_relevance"] > delivery["metric_relevance"]
    assert delivery["prevalence_unfiltered"] > sale["prevalence_unfiltered"]
    assert sale["postponement_rate"] > delivery["postponement_rate"]
    assert sale["rank_12m"] == 1
    assert sale["delay_mechanism"]
    assert "outranks" in (sale["comparison_notes"] or "")
    assert json.loads(sale["intent_vs_bookmark"])["bookmark_or_impulse"] == 0
    assert config.rank.export_path.exists()
    exported = json.loads(config.rank.export_path.read_text(encoding="utf-8"))
    assert exported[0]["opportunity_id"] == "wait_for_sale_sale_timing"
    conn.close()


def test_segment_slices_omitted_below_min_n(tmp_path: Path):
    config = _config(tmp_path)
    conn = connect(config.storage.path)
    init_db(conn)
    bounds = cutoffs(config, AS_OF)
    start_run(conn, run_id="r1", phase="rank", sources=["play"], config_snapshot={}, models=config.models.as_dict())
    ids = [
        _add_doc(
            conn,
            config,
            bounds,
            source="play",
            native=f"w{i}",
            text="Wishlist until EORS for a wedding look.",
            observed_at=AS_OF,
            relevant=True,
            jobs=["wait_for_sale"],
            blockers=["sale_timing"],
            postpone="yes",
            clues=["occasion:wedding"],
        )
        for i in range(5)
    ]
    replace_opportunity_areas(
        conn,
        "r1",
        [
            {
                "opportunity_id": "wait_for_sale_sale_timing",
                "cluster_version": "cluster_v1",
                "problem_one_liner": "Users wait for a sale.",
                "member_doc_ids": ids,
                "representative_doc_ids": ids[:1],
                "job_mix": {"wait_for_sale": 1.0},
                "blocker_mix": {"sale_timing": 1.0},
                "source_mix": {"play": 1.0},
                "single_source_warning": True,
                "quotes": [],
                "naming_source": "template",
            }
        ],
    )
    conn.commit()
    from phases.p5_rank.run import run

    run(conn, config=config, run_id="r1", collected_at=AS_OF, bounds=bounds, source_filter=[])
    row = fetch_opportunity_areas(conn)[0]
    assert json.loads(row["segment_slices"]) == []
    conn.close()


def test_rank_opportunities_requires_members():
    ranked = rank_opportunities(
        [{"opportunity_id": "empty", "member_doc_ids": ["missing"], "problem_one_liner": "x"}],
        {},
        n_relevant=1,
        n_unfiltered=1,
        bounds=cutoffs(load_config(), AS_OF),
        weights=load_config().rank,
    )
    assert ranked == []
    assert volume_order_differs(ranked) is False
