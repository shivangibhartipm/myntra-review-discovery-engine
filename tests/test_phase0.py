from __future__ import annotations

from datetime import datetime
from pathlib import Path

from review_engine.config import load_config
from review_engine.db import connect, init_db
from review_engine.pii import contains_pii, redact_text, scrub_payload
from review_engine.windows import assign_corpus_layer, cutoffs


def test_cutoffs_encode_12m_and_90d():
    config = load_config()
    as_of = datetime(2026, 8, 24, 12, 0, 0)
    bounds = cutoffs(config, collected_at=as_of)
    assert bounds.recency_start == datetime(2026, 5, 26, 12, 0, 0)
    assert bounds.primary_start == datetime(2025, 8, 24, 12, 0, 0)
    assert bounds.as_dict()["recency_start"].startswith("2026-05-26")
    assert bounds.as_dict()["primary_start"].startswith("2025-08-24")


def test_corpus_layer_uses_observed_at_not_collected_at():
    config = load_config()
    collected = datetime(2026, 8, 24)
    bounds = cutoffs(config, collected_at=collected)
    recent = assign_corpus_layer("play", datetime(2026, 8, 1), bounds)
    older = assign_corpus_layer("play", datetime(2026, 1, 1), bounds)
    too_old = assign_corpus_layer("play", datetime(2023, 1, 1), bounds)
    assert recent == "recency_90d"
    assert older == "primary_12m"
    assert too_old is None


def test_pii_redacts_email_and_drops_author():
    text = redact_text("Ping me at wait@example.com or +91 98765 43210")
    assert not contains_pii(text)
    assert "[redacted-email]" in text
    assert "[redacted-phone]" in text
    cleaned = scrub_payload({"author_name": "Priya", "email": "a@b.com", "id": "r1", "text": "ok"})
    assert "author_name" not in cleaned
    assert "email" not in cleaned
    assert cleaned["id"] == "r1"


def test_stub_collector_writes_valid_row(tmp_path: Path):
    from phases.p0_foundations.run import run
    from review_engine.db import start_run

    config = load_config()
    db_path = tmp_path / "engine.db"
    conn = connect(db_path)
    init_db(conn)
    collected_at = datetime(2026, 8, 24, 12, 0, 0)
    bounds = cutoffs(config, collected_at)
    start_run(
        conn,
        run_id="test-run",
        phase="foundations",
        sources=["stub"],
        config_snapshot={"windows": bounds.as_dict()},
        models=config.models.as_dict(),
    )
    counts_in, counts_out, errors, _notes = run(
        conn,
        config=config,
        run_id="test-run",
        collected_at=collected_at,
        bounds=bounds,
        source_filter=["stub"],
    )
    assert counts_in == 3
    assert counts_out == 3
    assert errors == 0

    row = conn.execute("SELECT * FROM raw_documents ORDER BY source_native_id").fetchone()
    assert row is not None
    required = {
        "doc_id",
        "source",
        "source_native_id",
        "observed_at",
        "collected_at",
        "text",
        "lang",
        "corpus_layer",
    }
    assert required.issubset(row.keys())
    assert row["source"] == "stub"
    assert row["corpus_layer"] == "recency_90d"
    assert "@" not in row["text"]
    assert "Priya" not in (row["text"] or "")

    n = conn.execute("SELECT COUNT(*) AS n FROM raw_documents").fetchone()["n"]
    assert n == 3
    conn.close()
