from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from review_engine.config import load_config
from review_engine.db import connect, init_db
from review_engine.pii import contains_pii
from review_engine.present.levers import suggested_lever
from review_engine.present.reports import ranked_markdown
from review_engine.windows import cutoffs

from test_phase5 import _seed_sale_vs_delivery

AS_OF = datetime(2026, 8, 24, 12, 0, 0)


def _config(tmp_path: Path):
    base = load_config()
    rank = replace(base.rank, export_path=tmp_path / "opportunities_ranked.json", min_segment_n=30)
    present = replace(
        base.present,
        export_path=tmp_path / "opportunities.json",
        quotes_dir=tmp_path / "quotes",
        report_dir=tmp_path / "reports",
        web_data_dir=tmp_path / "web" / "public" / "data",
        ranked_path=tmp_path / "opportunities_ranked.json",
        audit_path=tmp_path / "audit_snippets.jsonl",
    )
    storage = replace(base.storage, path=tmp_path / "engine.db")
    return replace(
        base,
        as_of=AS_OF,
        rank=rank,
        present=present,
        cluster=replace(base.cluster, use_embed=False, use_llm=False),
        extract=replace(base.extract, use_llm=False),
        filter=replace(base.filter, use_llm=False),
        storage=storage,
    )


def _rank_then_present(tmp_path: Path):
    config = _config(tmp_path)
    conn = connect(config.storage.path)
    init_db(conn)
    bounds, _, _ = _seed_sale_vs_delivery(conn, config)
    from phases.p5_rank.run import run as rank_run
    from phases.p6_present.run import run as present_run

    rank_run(conn, config=config, run_id="r1", collected_at=AS_OF, bounds=bounds, source_filter=[])
    counts_in, counts_out, errors, notes = present_run(
        conn,
        config=config,
        run_id="r2",
        collected_at=AS_OF,
        bounds=bounds,
        source_filter=[],
    )
    return config, conn, json.loads(notes), counts_in, counts_out, errors


def test_sale_wait_lever():
    copy = suggested_lever({"wait_for_sale": 1.0}, {"sale_timing": 1.0})
    assert "price-drop" in copy.lower() or "sale countdown" in copy.lower()


def test_present_writes_markdown_csv_json_and_quotes(tmp_path: Path):
    config, conn, report, counts_in, counts_out, errors = _rank_then_present(tmp_path)
    assert errors == 0
    assert counts_in == 2
    assert counts_out == 2
    assert report["top_opportunity_id"] == "wait_for_sale_sale_timing"

    md_path = config.present.report_dir / "ranked.md"
    csv_path = config.present.report_dir / "opportunities.csv"
    board_path = config.present.export_path
    assert md_path.exists()
    assert csv_path.exists()
    assert board_path.exists()

    md = md_path.read_text(encoding="utf-8")
    assert md.startswith("# Wishlist → purchase: within 30 days and overall")
    assert "Users wait for a sale before buying saved items." in md
    assert "waiting for the sale" in md
    assert "NPS" not in md
    assert "topic cloud" not in md.lower()
    assert "Corpus health" in md
    assert "Why do users add fashion products to their wishlist?" in md

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "rank_90d" in csv_text
    assert "wait_for_sale_sale_timing" in csv_text

    board = json.loads(board_path.read_text(encoding="utf-8"))
    assert "Wishlist" in board["headline"] and "30 days" in board["headline"]
    first = board["opportunities"][0]
    assert first["opportunity_id"] == "wait_for_sale_sale_timing"
    assert first["quotes"]
    assert first["suggested_lever"]
    assert first["plain"]["delay_strength"]
    assert first["plain"]["blocks_purchase_ever"]
    assert board["briefing"]["first_bet"]["opportunity_id"] == "wait_for_sale_sale_timing"
    assert [s["id"] for s in board["briefing"]["scenarios"]] == ["general", "within_30d"]
    qids = [q["id"] for q in board["briefing"]["questions"]]
    assert qids[0] == "why_wishlist"
    assert len(qids) == 9
    assert "uncertainties" not in qids
    assert "stops_purchase" in qids
    assert (config.present.web_data_dir / "opportunities.json").exists()
    conn.close()


def test_exports_have_no_pii(tmp_path: Path):
    config, conn, _, _, _, _ = _rank_then_present(tmp_path)
    board = json.loads(config.present.export_path.read_text(encoding="utf-8"))
    for opp in board["opportunities"]:
        for quote in opp["quotes"]:
            assert not contains_pii(quote["quote"])
        assert not contains_pii(opp["problem_one_liner"])
    for path in config.present.quotes_dir.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert not contains_pii(payload["quote"])
    conn.close()


def test_onepagers_written(tmp_path: Path):
    config, conn, _, _, _, _ = _rank_then_present(tmp_path)
    pages = list((config.present.report_dir / "onepagers").glob("*.md"))
    assert len(pages) == 2
    assert "30-day" in pages[0].read_text(encoding="utf-8")
    conn.close()


def test_empty_opportunities_message(tmp_path: Path):
    config = _config(tmp_path)
    conn = connect(config.storage.path)
    init_db(conn)
    bounds = cutoffs(config, AS_OF)
    from phases.p6_present.run import run

    _, counts_out, errors, notes = run(
        conn,
        config=config,
        run_id="empty",
        collected_at=AS_OF,
        bounds=bounds,
        source_filter=[],
    )
    assert errors == 0
    assert counts_out == 0
    report = json.loads(notes)
    assert "rank" in (report.get("message") or "").lower()
    md = (config.present.report_dir / "ranked.md").read_text(encoding="utf-8")
    assert "No ranked opportunities" in md
    conn.close()


def test_markdown_does_not_lead_with_nps():
    md = ranked_markdown(
        [
            {
                "rank_90d": 1,
                "volume_rank": 2,
                "opportunity_id": "wait_for_sale_sale_timing",
                "problem_one_liner": "Users wait for a sale before buying saved items.",
                "metric_relevance": 5,
                "prevalence_relevant": 0.2,
                "postponement_rate": 1.0,
                "delay_mechanism": "park until sale",
                "quotes": [
                    {
                        "doc_id": "abc",
                        "source": "play",
                        "observed_at": "2026-08-01",
                        "quote": "waiting for EORS",
                    }
                ],
                "suggested_lever": "Wishlist price-drop alerts / sale countdown on saved items",
                "job_mix": {"wait_for_sale": 1.0},
                "blocker_mix": {"sale_timing": 1.0},
                "source_mix": {"play": 1.0},
            }
        ]
    )
    assert md.splitlines()[0] == "# Wishlist → purchase: within 30 days and overall"
    assert "waiting for EORS" in md
    assert "Why do users add fashion products to their wishlist?" in md
    assert "NPS" not in md
    assert "Wishlist → purchase (in general)" in md
    assert "Within 30 days of saving" in md
