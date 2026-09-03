from review_engine.present.normalize import board_row


def test_board_row_excludes_stub_quotes_and_sources():
    raw = {
        "opportunity_id": "wait_for_sale_sale_timing",
        "problem_one_liner": "Users wait for a sale.",
        "member_n": 2,
        "member_doc_ids": ["play-1", "stub-1"],
        "job_mix": {"wait_for_sale": 1.0},
        "blocker_mix": {"sale_timing": 1.0},
        "source_mix": {"play": 0.5, "stub": 0.5},
        "quotes": [
            {"doc_id": "play-1", "source": "play", "observed_at": "2026-01-01", "quote": "Waiting for EORS sale."},
            {"doc_id": "stub-1", "source": "stub", "observed_at": "2026-01-02", "quote": "Added to wishlist until EORS."},
        ],
    }
    documents = {
        "play-1": {"source": "play", "text": "Waiting for EORS sale.", "corpus_layer": "recency_90d"},
        "stub-1": {"source": "stub", "text": "Added to wishlist until EORS.", "corpus_layer": "recency_90d"},
    }
    row = board_row(raw, documents=documents, enrichments={})
    assert row["member_n"] == 1
    assert row["member_doc_ids"] == ["play-1"]
    assert row["sources"] == ["play"]
    assert "stub" not in row["source_mix"]
    assert len(row["quotes"]) == 1
    assert row["quotes"][0]["source"] == "play"
