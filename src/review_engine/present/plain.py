"""Plain-language labels for the PM board. Scores stay in JSON; copy is for humans."""

from __future__ import annotations

from typing import Any, Mapping

JOB_LABELS = {
    "bookmark_later": "saving for later",
    "wait_for_sale": "waiting for a sale or price drop",
    "shortlist_compare": "comparing a few options before choosing",
    "intent_blocked": "wanting the item but getting stuck",
    "occasion_social": "waiting for an occasion or a friend’s opinion",
    "impulse_park": "saving something they liked in a photo",
    "unknown": "reason not clear from the comments",
}

BLOCKER_LABELS = {
    "fit": "fit",
    "size_chart": "size chart",
    "photo_mismatch": "photos vs real product",
    "fabric_quality": "fabric or quality",
    "price": "price",
    "sale_timing": "sale timing",
    "review_volume_trust": "review volume or trust",
    "authenticity": "authenticity",
    "returns": "returns",
    "delivery_checkout_saved": "delivery or checkout of a saved item",
    "styling_occasion": "styling or occasion",
    "social_validation": "friends’ opinions",
    "competitor_check": "checking a competitor",
}

ROLE_BLOCKERS = {
    "fit": ("fit",),
    "size": ("size_chart", "fit"),
    "styling": ("styling_occasion",),
    "price": ("price", "sale_timing"),
    "reviews": ("review_volume_trust",),
    "occasion": ("styling_occasion", "occasion_social"),
    "social validation": ("social_validation",),
}


def job_label(key: str) -> str:
    return JOB_LABELS.get(key, key.replace("_", " "))


def blocker_label(key: str) -> str:
    return BLOCKER_LABELS.get(key, key.replace("_", " "))


def pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{round(float(value) * 1000) / 10:.1f}%"


def delay_strength(metric_relevance: float | None) -> str:
    if metric_relevance is None:
        return "We don’t yet know how much this delays buying"
    score = float(metric_relevance)
    if score >= 5:
        return "This often stops people from buying within a month"
    if score >= 4:
        return "This often makes people wait more than a month"
    if score >= 3:
        return "This sometimes makes people wait, along with other reasons"
    return "People mention this a lot, but it doesn’t always delay buying"


def blocks_purchase_ever(metric_relevance: float | None) -> str:
    """Impact on wishlist→purchase in general (not only the 30-day clock)."""
    if metric_relevance is None:
        return "We don’t yet know how much this stops a saved item from becoming an order"
    score = float(metric_relevance)
    if score >= 5:
        return "This often stops people from buying a saved item at all"
    if score >= 4:
        return "This often keeps a saved item from becoming an order"
    if score >= 3:
        return "This sometimes blocks the buy, along with other reasons"
    return "People mention this a lot, but it doesn’t always block the buy"


def how_common(prevalence_relevant: float | None) -> str:
    if prevalence_relevant is None:
        return "We don’t yet know how common this is"
    share = float(prevalence_relevant)
    pretty = pct(share)
    if share >= 0.2:
        return f"One of the most common reasons people mention ({pretty})"
    if share >= 0.05:
        return f"A fairly common reason ({pretty})"
    return f"Less common, but still shows up ({pretty})"


def waiting_past_30d(postponement_rate: float | None) -> str:
    if postponement_rate is None:
        return "Comments don’t clearly say they wait more than a month"
    rate = float(postponement_rate)
    pretty = pct(rate)
    if rate >= 0.7:
        return f"Most comments here say people wait more than a month ({pretty})"
    if rate >= 0.3:
        return f"Some comments here say people wait more than a month ({pretty})"
    return f"Few comments clearly say they wait more than a month ({pretty})"


def mix_labels(mix: Mapping[str, Any] | None, *, kind: str) -> list[str]:
    if not isinstance(mix, dict):
        return []
    items = [(k, float(v or 0)) for k, v in mix.items() if v and k != "unknown"]
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    label = job_label if kind == "job" else blocker_label
    return [label(k) for k, _ in items]


def opportunity_plain(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "delay_strength": delay_strength(row.get("metric_relevance")),
        "blocks_purchase_ever": blocks_purchase_ever(row.get("metric_relevance")),
        "how_common": how_common(row.get("prevalence_relevant")),
        "waiting_past_30d": waiting_past_30d(row.get("postponement_rate")),
        "jobs": mix_labels(row.get("job_mix"), kind="job"),
        "blockers": mix_labels(row.get("blocker_mix"), kind="blocker"),
    }
