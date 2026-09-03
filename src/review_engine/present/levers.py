"""Hypothesis-only product levers. Not a committed roadmap."""

from __future__ import annotations

from typing import Mapping

# First matching rule wins.
_RULES: tuple[tuple[frozenset[str], frozenset[str], str], ...] = (
    (
        frozenset({"wait_for_sale"}),
        frozenset({"sale_timing", "price"}),
        "Wishlist price-drop alerts / sale countdown on saved items",
    ),
    (
        frozenset({"intent_blocked"}),
        frozenset({"size_chart", "fit"}),
        "Fit confidence on saved items (size recs, chart clarity)",
    ),
    (
        frozenset({"shortlist_compare"}),
        frozenset({"competitor_check"}),
        "Compare-saved-items across shortlisted SKUs",
    ),
    (
        frozenset(),
        frozenset({"photo_mismatch"}),
        "Better photos / haul proof on the PDP for saved items",
    ),
    (
        frozenset({"occasion_social"}),
        frozenset({"styling_occasion", "social_validation"}),
        "Social / occasion proof on saved items",
    ),
    (
        frozenset(),
        frozenset({"delivery_checkout_saved"}),
        "Checkout reliability on the saved cart / buy-from-wishlist path",
    ),
    (
        frozenset({"intent_blocked"}),
        frozenset({"returns", "authenticity"}),
        "Return and authenticity reassurance on wishlist checkout",
    ),
    (
        frozenset({"bookmark_later", "impulse_park"}),
        frozenset(),
        "Nudge saved-for-later items with a 30-day conversion prompt (hypothesis)",
    ),
)


def suggested_lever(job_mix: Mapping[str, float] | None, blocker_mix: Mapping[str, float] | None) -> str:
    jobs = {k for k, v in (job_mix or {}).items() if v}
    blockers = {k for k, v in (blocker_mix or {}).items() if v}
    for job_need, blocker_need, copy in _RULES:
        job_ok = not job_need or bool(jobs & job_need)
        blocker_ok = not blocker_need or bool(blockers & blocker_need)
        if job_ok and blocker_ok:
            return copy
    return "Hypothesis TBD — inspect quotes before committing a 30-day test"
