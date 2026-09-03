"""Tests for stuck-reason aggregation."""

from review_engine.present.stuck_reasons import stuck_reason_catalog, stuck_reason_mix, top_stuck_reason_labels


def test_stuck_reason_mix_from_member_text():
    documents = {
        "a": {"text": "Waiting for price drop on my wishlist items, too expensive right now."},
        "b": {"text": "Shortlisted two dresses but torn between them on Myntra vs Ajio."},
    }
    mix = stuck_reason_mix(["a", "b"], documents=documents, enrichments={})
    assert "price_value_hesitation" in mix
    assert "comparison_shopping" in mix


def test_top_stuck_reason_labels():
    mix = {"price_value_hesitation": 0.6, "comparison_shopping": 0.2}
    labels = top_stuck_reason_labels(mix)
    assert labels[0] == "Price / value hesitation"


def test_stuck_reason_catalog_counts_relevant_only():
    rows = [
        {"text": "Wishlist graveyard, never actually buy.", "is_relevant": True},
        {"text": "Great delivery experience.", "is_relevant": False},
    ]
    catalog = stuck_reason_catalog(rows, relevant_only=True)
    graveyard = next(row for row in catalog if row["id"] == "bookmark_not_buying")
    assert graveyard["count"] == 1
