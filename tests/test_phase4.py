from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from review_engine.cluster.embed import concat_vectors, tag_vector
from review_engine.cluster.group import Cluster, Member, split_mixed_clusters
from review_engine.cluster.pipeline import cluster_members, name_clusters
from review_engine.config import load_config
from review_engine.db import (
    connect,
    fetch_opportunity_areas,
    get_enrichment,
    init_db,
    start_run,
    upsert_document,
    upsert_enrichment_extract,
    upsert_enrichment_relevance,
)
from review_engine.records import build_canonical
from review_engine.windows import cutoffs

AS_OF = datetime(2026, 8, 24, 12, 0, 0)


def _config(tmp_path: Path):
    base = load_config()
    cluster = replace(
        base.cluster,
        use_embed=False,
        use_llm=False,
        skip_if_same_version=False,
        export_path=tmp_path / "opportunities.json",
        name_overrides_path=tmp_path / "overrides.json",
    )
    extract = replace(base.extract, use_llm=False)
    storage = replace(base.storage, path=tmp_path / "engine.db")
    return replace(
        base,
        as_of=AS_OF,
        cluster=cluster,
        extract=extract,
        filter=replace(base.filter, use_llm=False),
        storage=storage,
    )


def _member(doc_id, source, text, jobs, blockers, observed_at="2026-08-01"):
    vec = concat_vectors(
        tag_vector(jobs=jobs, blockers=blockers, postponement="unknown", text=text),
        None,
    )
    return Member(
        doc_id=doc_id,
        source=source,
        observed_at=observed_at,
        text=text,
        jobs=jobs,
        blockers=blockers,
        evidence_span=text[:80],
        postponement="yes" if "EORS" in text or "later" in text else "unknown",
        vector=vec,
    )


def _theme_members():
    return [
        _member("s1", "play", "Wishlist until EORS then I will buy.", ["wait_for_sale"], ["sale_timing"]),
        _member("s2", "reddit", "Waiting for the sale / EORS to order this.", ["wait_for_sale"], ["sale_timing"]),
        _member("s3", "youtube", "I added it for End of Reason Sale.", ["wait_for_sale"], ["sale_timing"]),
        _member("z1", "play", "Size chart is unclear so I will not buy yet.", ["intent_blocked"], ["size_chart"]),
        _member("z2", "reddit", "The size chart on Myntra is confusing.", ["intent_blocked"], ["size_chart"]),
        _member("z3", "youtube", "Don't know my size for this kurta.", ["intent_blocked"], ["fit"]),
        _member("c1", "reddit", "Confused between these two kurtas, which is better?", ["shortlist_compare"], ["competitor_check"]),
        _member("c2", "play", "Shortlist vs Ajio, cannot decide.", ["shortlist_compare"], ["competitor_check"]),
        _member("c3", "youtube", "Myntra or Ajio for this dress?", ["shortlist_compare"], ["competitor_check"]),
        _member("o1", "reddit", "Will this look good for a wedding?", ["occasion_social"], ["styling_occasion"]),
        _member("o2", "youtube", "Need an office look, not sure this works.", ["occasion_social"], ["styling_occasion"]),
        _member("o3", "play", "Shaadi outfit on wishlist, waiting for a friend's opinion.", ["occasion_social"], ["social_validation"]),
        _member("b1", "play", "Saving for later when I have money after salary.", ["bookmark_later"], ["price"]),
        _member("b2", "app_store", "Just bookmarking until next month.", ["bookmark_later"], ["price"]),
        _member("b3", "reddit", "Wishlist is a bookmark, not buying now.", ["bookmark_later"], ["price"]),
        _member("d1", "play", "Wishlist checkout payment failed on my saved item.", ["intent_blocked"], ["delivery_checkout_saved"]),
        _member("d2", "play", "Cannot complete checkout for a wishlisted product.", ["intent_blocked"], ["delivery_checkout_saved"]),
        _member("d3", "play", "Payment on saved item keeps failing.", ["intent_blocked"], ["delivery_checkout_saved"]),
        _member("p1", "youtube", "Looks different in the haul video so waiting.", ["intent_blocked"], ["photo_mismatch"]),
        _member("p2", "reddit", "Photo mismatch, not like the pic.", ["intent_blocked"], ["photo_mismatch"]),
        _member("p3", "play", "Looks different than photos, parked on list.", ["intent_blocked"], ["photo_mismatch"]),
        _member("a1", "play", "Worried it is fake, will not buy until sure.", ["intent_blocked"], ["authenticity"]),
        _member("a2", "reddit", "Authenticity concerns, might be replica.", ["intent_blocked"], ["authenticity"]),
        _member("a3", "youtube", "Is this fake on Myntra?", ["intent_blocked"], ["authenticity"]),
    ]


def test_split_sale_wait_from_delivery():
    mixed = Cluster(
        label="mixed",
        members=[
            _member("s", "reddit", "Waiting for EORS.", ["wait_for_sale"], ["sale_timing"]),
            _member("t", "play", "Waiting for the sale.", ["wait_for_sale"], ["sale_timing"]),
            _member("d", "play", "Wishlist checkout failed.", ["intent_blocked"], ["delivery_checkout_saved"]),
            _member("e", "play", "Payment on saved item failed.", ["intent_blocked"], ["delivery_checkout_saved"]),
        ],
    )
    split = split_mixed_clusters([mixed])
    assert len(split) == 2
    jobs = {tuple(sorted(set(c.job_values()))) for c in split}
    blockers = {tuple(sorted(set(c.blocker_values()))) for c in split}
    assert any("wait_for_sale" in j for j in jobs)
    assert any("delivery_checkout_saved" in b for b in blockers)


def test_size_chart_and_dont_know_size_merge():
    clusters = cluster_members(_theme_members(), min_k=5, max_k=12, min_size=2, merge_cosine=0.88)
    size_cluster = next(
        (
            c
            for c in clusters
            if "size_chart" in c.blocker_values() and set(c.blocker_values()) <= {"fit", "size_chart"}
        ),
        None,
    )
    assert size_cluster is not None
    ids = {m.doc_id for m in size_cluster.members}
    assert {"z1", "z2", "z3"} <= ids


def test_named_clusters_are_distinct_and_not_miscellaneous(tmp_path: Path):
    config = _config(tmp_path)
    clusters = cluster_members(_theme_members(), min_k=5, max_k=12, min_size=2, merge_cosine=0.88)
    named = name_clusters(clusters, config=config, use_llm=False)
    names = [o.problem_one_liner.lower() for o in named]
    assert 5 <= len(named) <= 12
    assert len(set(names)) == len(names)
    assert all("miscellaneous" not in n for n in names)
    for opp in named:
        sources = {q["source"] for q in opp.quotes}
        if len(sources) < 2:
            assert opp.single_source_warning
        else:
            assert not opp.single_source_warning


def test_name_override(tmp_path: Path):
    config = _config(tmp_path)
    clusters = cluster_members(_theme_members(), min_k=5, max_k=12, min_size=2, merge_cosine=0.88)
    named = name_clusters(clusters, config=config, use_llm=False)
    target = named[0].opportunity_id
    config.cluster.name_overrides_path.write_text(
        json.dumps({target: "Users wait for EORS before converting a wishlist add."}),
        encoding="utf-8",
    )
    renamed = name_clusters(clusters, config=config, use_llm=False)
    match = next(o for o in renamed if o.opportunity_id == target)
    assert match.problem_one_liner.startswith("Users wait for EORS")
    assert match.naming_source == "override"


def _seed(conn, config, items):
    bounds = cutoffs(config, AS_OF)
    start_run(
        conn,
        run_id="c1",
        phase="cluster",
        sources=["play"],
        config_snapshot={},
        models=config.models.as_dict(),
    )
    for source, native, text, jobs, blockers in items:
        doc = build_canonical(
            source=source,
            collected_at=AS_OF,
            bounds=bounds,
            text=text,
            source_native_id=native,
            observed_at=AS_OF,
            lang="en",
        )
        upsert_document(conn, doc, "c1")
        upsert_enrichment_relevance(
            conn,
            doc_id=doc.doc_id,
            is_relevant=True,
            relevance_score=0.9,
            relevance_reasons=["wishlist_language"],
            filter_version="filter_v1",
        )
        upsert_enrichment_extract(
            conn,
            doc_id=doc.doc_id,
            claims=[{"doc_id": doc.doc_id, "jobs": jobs, "blockers": blockers}],
            jobs=jobs,
            blockers=blockers,
            postponement_beyond_30d="unknown",
            outside_myntra_info_seeking=False,
            segment_clues=[],
            confidence=0.8,
            evidence_span=text[:40],
            extract_version=config.extract.version,
        )
    conn.commit()
    return bounds


def test_phase4_persists_opportunities_and_assignments(tmp_path: Path):
    config = _config(tmp_path)
    conn = connect(config.storage.path)
    init_db(conn)
    corpus = [
        ("play", "s1", "Added to wishlist until EORS.", ["wait_for_sale"], ["sale_timing"]),
        ("reddit", "s2", "Waiting for the sale to buy this.", ["wait_for_sale"], ["sale_timing"]),
        ("play", "z1", "Size chart is unclear so I will not buy yet.", ["intent_blocked"], ["size_chart"]),
        ("reddit", "z2", "Don't know my size, size chart confusing.", ["intent_blocked"], ["size_chart"]),
        ("reddit", "c1", "Confused between these two kurtas.", ["shortlist_compare"], ["competitor_check"]),
        ("youtube", "c2", "Myntra or Ajio which is better?", ["shortlist_compare"], ["competitor_check"]),
        ("reddit", "o1", "Will this look good for a wedding?", ["occasion_social"], ["styling_occasion"]),
        ("youtube", "o2", "Need this for office look.", ["occasion_social"], ["styling_occasion"]),
        ("play", "b1", "Saving for later when I have money.", ["bookmark_later"], ["price"]),
        ("app_store", "b2", "Just bookmarking until salary.", ["bookmark_later"], ["price"]),
        ("play", "d1", "Wishlist checkout payment failed.", ["intent_blocked"], ["delivery_checkout_saved"]),
        ("play", "d2", "Cannot checkout my saved item.", ["intent_blocked"], ["delivery_checkout_saved"]),
        ("youtube", "p1", "Looks different in the haul video.", ["intent_blocked"], ["photo_mismatch"]),
        ("reddit", "p2", "Photo mismatch, not like the pic.", ["intent_blocked"], ["photo_mismatch"]),
        ("play", "a1", "Worried it is fake.", ["intent_blocked"], ["authenticity"]),
        ("reddit", "a2", "Authenticity replica concern.", ["intent_blocked"], ["authenticity"]),
    ]
    bounds = _seed(conn, config, corpus)

    from phases.p4_cluster.run import run

    counts_in, counts_out, errors, notes = run(
        conn,
        config=config,
        run_id="c1",
        collected_at=AS_OF,
        bounds=bounds,
        source_filter=[],
    )
    report = json.loads(notes)
    assert errors == 0
    assert counts_in == 16
    assert 5 <= counts_out <= 12
    rows = fetch_opportunity_areas(conn)
    assert len(rows) == counts_out
    names = [row["problem_one_liner"] for row in rows]
    assert len(set(names)) == len(names)
    assert all("miscellaneous" not in n.lower() for n in names)
    for row in rows:
        members = json.loads(row["member_doc_ids"])
        mix = json.loads(row["source_mix"])
        assert members
        if len(mix) < 2:
            assert row["single_source_warning"] == 1
        quotes = json.loads(row["quotes"])
        assert quotes
        for quote in quotes:
            assert quote["doc_id"]
            assert quote["quote"]
    sample_id = conn.execute("SELECT doc_id FROM document_enrichment LIMIT 1").fetchone()["doc_id"]
    sample = get_enrichment(conn, sample_id)
    assert sample["cluster_id"]
    assert sample["cluster_version"] == config.cluster.version
    assert config.cluster.export_path.exists()
    assert report["distinct_names"] == counts_out
    conn.close()
