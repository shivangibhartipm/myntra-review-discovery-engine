"""Metric-relevance (1–5) and actionability (0–1) rubrics for wishlist conversion.

These are proxies: public text cannot join to a Myntra wishlist add.
Scores encode how clearly a theme delays or blocks purchase within 30 days of add,
and whether Myntra can change it in product, pricing, merchandising, or CX.
"""

from __future__ import annotations

from review_engine.extract.taxonomy import BLOCKERS, JOBS

# Explicit 30-day clock (sale wait) outranks loud post-purchase noise (generic delivery).
JOB_METRIC_RELEVANCE = {
    "wait_for_sale": 5,
    "intent_blocked": 4,
    "shortlist_compare": 4,
    "bookmark_later": 3,
    "occasion_social": 3,
    "impulse_park": 2,
    "unknown": 2,
}

BLOCKER_METRIC_RELEVANCE = {
    "sale_timing": 5,
    "size_chart": 4,
    "fit": 4,
    "photo_mismatch": 4,
    "authenticity": 4,
    "returns": 4,
    "price": 4,
    "review_volume_trust": 3,
    "competitor_check": 3,
    "styling_occasion": 3,
    "social_validation": 3,
    "delivery_checkout_saved": 2,  # often loud, weakly causal for *saved-item* conversion
    "fabric_quality": 2,
}

JOB_ACTIONABILITY = {
    "wait_for_sale": 0.85,
    "intent_blocked": 0.9,
    "shortlist_compare": 0.8,
    "bookmark_later": 0.7,
    "occasion_social": 0.65,
    "impulse_park": 0.4,
    "unknown": 0.4,
}

BLOCKER_ACTIONABILITY = {
    "size_chart": 0.95,
    "fit": 0.9,
    "photo_mismatch": 0.85,
    "sale_timing": 0.85,
    "price": 0.85,
    "review_volume_trust": 0.8,
    "returns": 0.8,
    "authenticity": 0.75,
    "delivery_checkout_saved": 0.7,
    "styling_occasion": 0.7,
    "social_validation": 0.65,
    "fabric_quality": 0.55,
    "competitor_check": 0.5,
}

DELAY_COPY = {
    ("wait_for_sale", "sale_timing"): (
        "Users park saved items until a sale window (EORS / price drop), so purchase slips past 30 days by design."
    ),
    ("wait_for_sale", None): (
        "Users wait for a cheaper price on a saved item, stretching the add-to-buy clock beyond 30 days."
    ),
    ("intent_blocked", "size_chart"): (
        "Buyers want the SKU but will not check out until size/fit is trustworthy, so the wishlist ages out."
    ),
    ("intent_blocked", "fit"): (
        "Fit uncertainty stops checkout of an otherwise intended saved item within 30 days."
    ),
    ("intent_blocked", "photo_mismatch"): (
        "Photo/haul mismatch keeps shoppers from converting a saved item until they see more proof."
    ),
    ("intent_blocked", "returns"): (
        "Return-policy risk blocks checkout of a saved item even when intent is high."
    ),
    ("intent_blocked", "authenticity"): (
        "Fear of fakes delays or cancels purchase of a shortlisted item inside 30 days."
    ),
    ("intent_blocked", "delivery_checkout_saved"): (
        "Checkout or delivery failure on a saved item can kill conversion, but many delivery rants are weakly tied to wishlist add."
    ),
    ("shortlist_compare", None): (
        "Choice paralysis across shortlisted products postpones the buy until a comparison is resolved."
    ),
    ("bookmark_later", "price"): (
        "The list is used as a bookmark until money or salary arrives, often after the 30-day window."
    ),
    ("bookmark_later", None): (
        "Saving is bookmarking, not near-term purchase intent, so 30-day conversion stays low."
    ),
    ("impulse_park", None): (
        "Items parked from a photo have little true intent, so 30-day conversion is unlikely even if volume is high."
    ),
    ("occasion_social", None): (
        "Shoppers wait for occasion or social confidence before buying a saved look, which can miss a 30-day clock."
    ),
}


def dominant_key(mix: dict[str, float], allowed: tuple[str, ...]) -> str | None:
    ranked = [(name, share) for name, share in mix.items() if name in allowed and name != "unknown"]
    if not ranked:
        ranked = [(name, share) for name, share in mix.items() if name in allowed]
    if not ranked:
        return None
    ranked.sort(key=lambda kv: (-kv[1], kv[0]))
    return ranked[0][0]


def metric_relevance(job_mix: dict[str, float], blocker_mix: dict[str, float]) -> float:
    job = dominant_key(job_mix, JOBS)
    blocker = dominant_key(blocker_mix, BLOCKERS)
    scores = []
    if job:
        scores.append(JOB_METRIC_RELEVANCE.get(job, 2))
    if blocker:
        scores.append(BLOCKER_METRIC_RELEVANCE.get(blocker, 2))
    if not scores:
        return 2.0
    # Sale-wait must beat generic delivery even if both appear in mix.
    if job == "wait_for_sale" or blocker == "sale_timing":
        return 5.0
    if blocker == "delivery_checkout_saved" and job not in {"intent_blocked", "wait_for_sale"}:
        return 2.0
    return float(max(scores))


def actionability(job_mix: dict[str, float], blocker_mix: dict[str, float]) -> float:
    job = dominant_key(job_mix, JOBS)
    blocker = dominant_key(blocker_mix, BLOCKERS)
    scores = []
    if job:
        scores.append(JOB_ACTIONABILITY.get(job, 0.4))
    if blocker:
        scores.append(BLOCKER_ACTIONABILITY.get(blocker, 0.4))
    if not scores:
        return 0.4
    return round(sum(scores) / len(scores), 4)


def delay_mechanism(job_mix: dict[str, float], blocker_mix: dict[str, float]) -> str:
    job = dominant_key(job_mix, JOBS)
    blocker = dominant_key(blocker_mix, BLOCKERS)
    if (job, blocker) in DELAY_COPY:
        return DELAY_COPY[(job, blocker)]
    if (job, None) in DELAY_COPY:
        return DELAY_COPY[(job, None)]
    return (
        "This theme may delay a saved-item purchase, but the 30-day mechanism is weaker or mixed; "
        "treat volume as a loudness diagnostic rather than a conversion lever."
    )


def loud_but_weak_penalty(prevalence_unfiltered: float, metric_rel: float) -> float:
    """High unfiltered share with weak metric relevance (the delivery-complaint case)."""
    if metric_rel >= 4:
        return 0.0
    weakness = (4.0 - metric_rel) / 3.0  # 1.0 at relevance 1, ~0.33 at 3
    return round(min(1.0, max(0.0, prevalence_unfiltered * weakness)), 4)
