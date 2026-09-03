"""Tests for categorized wishlist behavioral themes."""

from review_engine.relevance.lexical import lexical_gate
from review_engine.relevance.pipeline import classify_text
from review_engine.wishlist_themes import (
    BLOCKER_THEME_IDS,
    detect_wishlist_themes,
    theme_clues,
)
from review_engine.extract.lexical import extract_lexical
from review_engine.config import load_config
from dataclasses import replace


def test_fit_size_theme():
    text = "Not sure about the size — size chart confusing on this brand."
    themes = detect_wishlist_themes(text)
    assert "fit_size_uncertainty" in themes


def test_price_theme():
    text = "Waiting for price drop, too expensive right now for my budget."
    themes = detect_wishlist_themes(text)
    assert "price_value_hesitation" in themes


def test_comparison_theme():
    text = "Torn between two kurtas — Myntra vs Ajio, which one should I buy?"
    themes = detect_wishlist_themes(text)
    assert "comparison_shopping" in themes


def test_competitor_delivery_complaint_not_comparison():
    text = (
        "Worst app ever. Never try to order from this app, flipkart, amazon even meesho "
        "have better service. My order was cancelled and delivery was horrible."
    )
    assert "comparison_shopping" not in detect_wishlist_themes(text)


def test_competitor_with_save_context_counts_as_comparison():
    text = "Shortlisted two dresses but found same product on Ajio cheaper, torn between them."
    assert "comparison_shopping" in detect_wishlist_themes(text)


def test_bookmark_graveyard_theme():
    text = "My wishlist is just a graveyard, I never actually buy anything."
    themes = detect_wishlist_themes(text)
    assert "bookmark_not_buying" in themes


def test_conversion_theme():
    text = "Finally bought from my wishlist after price dropped on sale."
    themes = detect_wishlist_themes(text)
    assert "trigger_to_purchase" in themes
    assert "price_value_hesitation" in themes


def test_ux_friction_theme():
    text = "No price alert on wishlist items, wish I could filter my wishlist."
    themes = detect_wishlist_themes(text)
    assert "wishlist_ux_friction" in themes


def test_user_phrase_examples():
    samples = {
        "fit_size_uncertainty": "Not sure about the size — size chart confusing across brands.",
        "price_value_hesitation": "Saving up for this kurta, will buy during end of season sale.",
        "styling_occasion_uncertainty": "Saving for a wedding but not sure how to style it.",
        "social_validation_review": "Does anyone have this? Need reviews before buying.",
        "trust_quality_doubt": "Saved this but fabric feels cheap in photos vs real product.",
        "comparison_shopping": "Torn between two options — found same product on Ajio cheaper.",
        "stock_availability": "My wishlist item is out of stock, notify me when back in stock.",
        "bookmark_not_buying": "Wishlist is just a graveyard — I hoard 100+ items and never buy.",
        "trigger_to_purchase": "Finally bought from wishlist after price dropped.",
        "wishlist_ux_friction": "Wishlist doesn't let me filter and no price alert on wishlist.",
        "post_purchase_validation": "Hesitated for so long but no regrets buying this.",
    }
    for theme_id, text in samples.items():
        assert theme_id in detect_wishlist_themes(text), theme_id


def test_stock_delivery_noise_excluded():
    text = (
        "Horrible delivery, contacted Myntra customer support twice. "
        "Order delayed and customer service is trash."
    )
    assert "stock_availability" not in detect_wishlist_themes(text)


def test_runs_small_needs_context():
    assert "fit_size_uncertainty" not in detect_wishlist_themes("Runs small, returned it.")
    assert "fit_size_uncertainty" in detect_wishlist_themes(
        "Shortlisted but runs small on this brand, afraid it won't fit before I order."
    )


def test_extract_adds_theme_clues():
    claim = extract_lexical("Waiting for EORS sale, wishlist full of items.")
    assert any(c.startswith("theme:") for c in claim.segment_clues)


def test_relevance_save_behavior_theme():
    config = load_config()
    config = replace(config, filter=replace(config.filter, use_llm=False))
    result = classify_text("Wishlist graveyard — I hoard items and never buy.", config)
    assert result.is_relevant
    assert "save_behavior_theme" in result.relevance_reasons


def test_blocker_themes_cover_user_categories():
    expected = {
        "fit_size_uncertainty",
        "price_value_hesitation",
        "styling_occasion_uncertainty",
        "social_validation_review",
        "trust_quality_doubt",
        "comparison_shopping",
        "stock_availability",
        "bookmark_not_buying",
    }
    assert expected <= BLOCKER_THEME_IDS


def test_theme_clues_format():
    assert theme_clues(["price_value_hesitation"]) == ["theme:price_value_hesitation"]
