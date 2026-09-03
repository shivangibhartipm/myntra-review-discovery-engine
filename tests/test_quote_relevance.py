from review_engine.present.quote_relevance import (
    _display_fallback_snippet,
    filter_quotes_for_opportunity,
    fill_topic_quotes,
    polish_quote,
    quote_is_relevant,
)
from review_engine.wishlist_context import quote_has_saved_item_context


def test_delivery_quote_rejected_for_price_topic():
    quote = "I am very disappointed with Myntra's delivery service.Whenever I place an order,"
    assert not quote_is_relevant(quote, blockers=["price"], full_text=quote)


def test_price_quote_accepted_for_price_topic():
    quote = "Saved it in wishlist but the price is too expensive right now."
    assert quote_is_relevant(quote, blockers=["price"], full_text=quote)


def test_filter_quotes_drops_off_topic():
    quotes = [
        {
            "doc_id": "a",
            "source": "play",
            "observed_at": "2026-01-01",
            "quote": "I am very disappointed with Myntra's delivery service.",
        },
        {
            "doc_id": "b",
            "source": "play",
            "observed_at": "2026-01-02",
            "quote": "Wishlist item is overpriced compared to last week.",
        },
    ]
    kept = filter_quotes_for_opportunity(quotes, blocker_mix={"price": 1.0})
    assert len(kept) == 1
    assert kept[0]["doc_id"] == "b"


def test_cancellation_quote_rejected_for_price_topic():
    quote = "Very disappointing experience with Myntra. I ordered 5 Libas sarees at an offer "
    full = (
        quote
        + "price, and all 5 were confirmed and shipped. Later, Myntra automatically cancelled them."
    )
    assert not quote_is_relevant(quote, blockers=["price"], full_text=full)


def test_price_only_topic_requires_save_or_hesitation_context():
    quote = "g a technical issue. I requested the same offer/price or compensation for the price difference."
    assert not quote_is_relevant(quote, blockers=["price"], full_text=quote)


def test_wishlist_price_quote_accepted():
    quote = "if i put anything on wishlist today the next day price of the product will increase"
    assert quote_is_relevant(quote, blockers=["price"], full_text=quote)


def test_positive_fabric_quote_rejected_for_fabric_topic():
    quote = "Perfect Fit, Quality Fabric"
    assert not quote_is_relevant(quote, blockers=["fabric_quality"], full_text=quote)


def test_positive_quality_quote_rejected_for_fabric_topic():
    quotes = [{"doc_id": "x", "source": "play", "observed_at": "", "quote": "wonderful quality. perfect size."}]
    kept = filter_quotes_for_opportunity(quotes, blocker_mix={"fabric_quality": 1.0})
    assert len(kept) == 0


def test_fill_topic_quotes_mines_from_members():
    documents = {
        "d1": {
            "source": "play",
            "observed_at": "2026-01-01",
            "text": "I added this kurta to my wishlist but the price feels too high right now.",
        },
        "d2": {
            "source": "play",
            "observed_at": "2026-01-02",
            "text": "Wishlist price keeps increasing every day. Waiting for a sale.",
        },
    }
    filled = fill_topic_quotes(
        [],
        member_doc_ids=["d1", "d2"],
        blocker_mix={"price": 1.0},
        documents=documents,
        enrichments={},
        min_quotes=2,
    )
    assert len(filled) >= 2
    assert all("price" in q["quote"].lower() or "wishlist" in q["quote"].lower() for q in filled)


def test_filter_prefers_evidence_span():
    quotes = [{"doc_id": "c", "source": "play", "observed_at": "", "quote": "Bad delivery again."}]
    documents = {
        "c": {
            "text": "Bad delivery again. I saved shoes but price is too high for now.",
        }
    }
    enrichments = {"c": {"evidence_span": "price is too high", "blockers": ["price"]}}
    kept = filter_quotes_for_opportunity(
        quotes,
        blocker_mix={"price": 1.0},
        documents=documents,
        enrichments=enrichments,
    )
    assert len(kept) == 1
    assert "price" in kept[0]["quote"].lower()
    assert quote_has_saved_item_context(kept[0]["quote"])


def test_generic_discount_quote_rejected():
    quote = "The only thing that makes this app interesting is the discount codes that they offer."
    assert not quote_is_relevant(quote, jobs=["wait_for_sale"], blockers=["sale_timing"], full_text=quote)


def test_delivery_postponed_quote_rejected():
    quote = "The products never get delivered. Everyday the dates keep on getting postponed."
    assert not quote_is_relevant(quote, blockers=["photo_mismatch"], full_text=quote)


def test_price_without_wishlist_context_rejected():
    quote = "and then the same product available in higher price!"
    assert not quote_is_relevant(quote, blockers=["price"], full_text=quote)


def test_polish_quote_expands_to_word_boundary():
    full = (
        "Added to wishlist but waiting...."
        "and then the same product available in higher price!"
    )
    rough = "e product available in higher price!"
    polished = polish_quote(rough, full)
    assert quote_has_saved_item_context(polished)
    assert "wishlist" in polished.lower() or "saved" in polished.lower()


def test_display_fallback_requires_saved_item_context():
    full = (
        "they fake coupons to lure customers then cancelled the order later...."
        "and then the same product available in higher price!"
    )
    assert _display_fallback_snippet(full, ["price"]) == ""
