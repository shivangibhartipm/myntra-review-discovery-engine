from dataclasses import replace

from review_engine.config import load_config
from review_engine.present.quote_relevance import quote_is_relevant
from review_engine.relevance.lexical import lexical_gate
from review_engine.relevance.pipeline import classify_text
from review_engine.wishlist_context import (
    fabric_quality_blocks_saved_purchase,
    fit_blocks_saved_purchase,
    fit_uncertainty_signal,
    quote_has_saved_item_context,
)


def test_post_purchase_return_refund_is_not_saved_item_blocker():
    text = "Maine return kar diya lekin abhi tak refund nhi mila, February se wait kar rahi hoon."
    assert not fit_blocks_saved_purchase(text)


def test_return_policy_with_purchase_intent_counts():
    text = "I love this kurta but the return policy worries me before I order."
    from review_engine.wishlist_context import returns_blocks_saved_purchase

    assert returns_blocks_saved_purchase(text)


def test_wishlist_return_hesitation_counts():
    text = "Added to wishlist but afraid returns will be a hassle if size is wrong."
    from review_engine.wishlist_context import returns_blocks_saved_purchase

    assert returns_blocks_saved_purchase(text)


def test_post_purchase_return_not_relevant_to_corpus():
    config = load_config()
    config = replace(config, filter=replace(config.filter, use_llm=False))
    text = "Returned the product in February and still no refund from Myntra."
    result = classify_text(text, config)
    assert result.is_relevant is False
    assert "returns_trust" not in result.relevance_reasons


def test_positive_fit_quality_review_not_relevant():
    config = load_config()
    config = replace(config, filter=replace(config.filter, use_llm=False))
    text = "Wonderful quality. Perfect size and giving glorious look."
    result = classify_text(text, config)
    assert result.is_relevant is False
    assert "fit_uncertainty" not in result.relevance_reasons


def test_wrong_size_delivery_not_fit_blocker():
    text = "Worst app. Seller sent wrong size products and platform charged me, no refund."
    assert not fit_blocks_saved_purchase(text)


def test_size_chart_shortlist_is_fit_blocker():
    text = "Confused between two pairs on my shortlist. Size chart is unclear so I have not ordered."
    assert fit_blocks_saved_purchase(text)


def test_wont_buy_until_size_is_fit_blocker():
    text = "Won't buy until I know the size. The size chart is useless."
    assert fit_blocks_saved_purchase(text)


def test_positive_fabric_quote_not_fabric_blocker():
    text = "Very nice fabric and size is well fitted"
    assert not fabric_quality_blocks_saved_purchase(text)


def test_fabric_hesitation_before_buy_counts():
    text = "Saved this dress but not sure about fabric quality before I order."
    assert fabric_quality_blocks_saved_purchase(text)


def test_lexical_gate_does_not_tag_positive_review():
    result = lexical_gate("Wonderful quality. Perfect size and giving glorious look.")
    assert "fit_uncertainty" not in result.tags


def test_fit_uncertainty_signal_requires_hesitation():
    assert not fit_uncertainty_signal("Good fabric good size")
    assert fit_uncertainty_signal("Won't buy until I know the size.")


def test_return_policy_quote_rejected_for_returns_topic():
    from review_engine.wishlist_context import returns_blocks_saved_purchase

    quote = "return kar diya lekin abhi tak refund nhi mila hai mujhe"
    assert not returns_blocks_saved_purchase(quote)
    assert not quote_is_relevant(quote, blockers=["returns"], full_text=quote)


def test_saved_item_return_quote_accepted():
    quote = "Saved in wishlist but return policy scares me from ordering."
    assert quote_is_relevant(quote, blockers=["returns"], full_text=quote)


def test_positive_fabric_quote_rejected_for_fabric_topic():
    quote = "Perfect Fit, Quality Fabric"
    assert not quote_is_relevant(quote, blockers=["fabric_quality"], full_text=quote)


def test_dont_hesitate_quality_praise_not_fabric_blocker():
    text = "Don't hesitate for the quality just order and enjoy it. I will definitely recommend it."
    assert not fabric_quality_blocks_saved_purchase(text)


def test_fantastic_quality_praise_not_fabric_blocker():
    text = "The quality of the products is fantastic no doubt!!!!!!!!"
    assert not fabric_quality_blocks_saved_purchase(text)


def test_not_sure_quality_without_save_context_not_blocker():
    text = "Variations of clothes are amazing but I am not sure about the quality other than that it was good"
    assert not fabric_quality_blocks_saved_purchase(text)


def test_size_quote_accepted_for_fit_topic():
    quote = "Shortlisted two kurtas but size chart is unclear so I have not ordered."
    assert quote_is_relevant(quote, blockers=["fit"], full_text=quote)


def test_saved_item_fabric_hesitation_counts():
    text = "Saved this dress but not sure about fabric quality before I order."
    assert fabric_quality_blocks_saved_purchase(text)


def test_quote_has_saved_item_context():
    assert quote_has_saved_item_context("Wishlist and waiting for discounts")
    assert quote_has_saved_item_context("Saved in wishlist but price is too high.")
    assert quote_has_saved_item_context("I saved shoes but price is too high for now.")
    assert quote_has_saved_item_context("Confused between two pairs on my shortlist.")
    assert not quote_has_saved_item_context("which one should I refer? Please suggest")
    assert not quote_has_saved_item_context(
        "In which one has crossed threshold delivary date to deliver , extra of 3 days"
    )
    assert not quote_has_saved_item_context("The only thing interesting is discount codes in special events.")
    assert not quote_has_saved_item_context("and then the same product available in higher price!")
    assert not quote_has_saved_item_context("Delivery was postponed again and again.")
