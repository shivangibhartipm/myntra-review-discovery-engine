"""Categorized wishlist / saved-item behavioral themes for tagging why an item is stuck."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal

from review_engine.wishlist_context import (
    _COMPARE_CONTEXT,
    _SAVED_OR_DELAY,
    fabric_quality_blocks_saved_purchase,
    fit_blocks_saved_purchase,
    returns_blocks_saved_purchase,
)

ThemeCategory = Literal["blocker", "conversion", "ux", "validation"]


def _p(*parts: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.I) for p in parts)


@dataclass(frozen=True)
class ThemeSpec:
    id: str
    category: ThemeCategory
    label: str
    patterns: tuple[re.Pattern[str], ...]
    contextual_patterns: tuple[re.Pattern[str], ...] = ()
    jobs: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    requires_save_context: bool = False


THEME_SPECS: tuple[ThemeSpec, ...] = (
    ThemeSpec(
        id="fit_size_uncertainty",
        category="blocker",
        label="Fit & size uncertainty",
        patterns=_p(
            r"not sure about the size",
            r"afraid it won'?t fit",
            r"size chart (?:is )?(?:confus|unclear|wrong|useless)",
            r"size chart confusing",
            r"different sizes in different brands",
            r"should i order a size up",
            r"return if (?:it )?doesn'?t fit",
            r"waiting to try (?:it )?in store",
            r"won'?t buy until.{0,30}size",
            r"don'?t know (?:my )?size",
        ),
        contextual_patterns=_p(
            r"runs small",
            r"runs large",
            r"true to size",
            r"\bsize up\b",
            r"\bsize down\b",
        ),
        jobs=("intent_blocked", "shortlist_compare"),
        blockers=("fit", "size_chart"),
    ),
    ThemeSpec(
        id="price_value_hesitation",
        category="blocker",
        label="Price / value hesitation",
        patterns=_p(
            r"wait(?:ing)? for (?:the )?sale",
            r"wait(?:ing)? for (?:a )?price drop",
            r"too expensive right now",
            r"will buy during (?:the )?sale",
            r"end of season sale",
            r"discount code",
            r"not worth full price",
            r"cheaper on (?:ajio|amazon|nykaa|meesho|flipkart)",
            r"saving up for",
            r"next paycheck",
            r"\beors\b",
            r"when i have (?:money|salary)",
            r"price (?:increase|higher).{0,40}wishlist",
            r"wishlist.{0,40}(?:expensive|price|cost)",
            r"wait(?:ing)? for (?:a )?(?:coupon|discount|offer)",
            r"too expensive(?:\s+right now)?",
            r"will buy (?:during|in) (?:the )?sale",
        ),
        contextual_patterns=_p(
            r"\bbudget\b",
            r"\bcoupon\b",
        ),
        jobs=("wait_for_sale", "bookmark_later"),
        blockers=("price", "sale_timing", "competitor_check"),
        requires_save_context=True,
    ),
    ThemeSpec(
        id="styling_occasion_uncertainty",
        category="blocker",
        label="Styling / occasion uncertainty",
        patterns=_p(
            r"not sure how to style",
            r"what to pair with",
            r"don'?t know when i'?d wear",
            r"saving for (?:a )?(?:wedding|party|occasion|festive|diwali)",
            r"don'?t need it right now",
            r"outfit inspo",
            r"styling ideas",
            r"impulse add",
            r"office look|office wear",
            r"\bwedding\b|shaadi",
        ),
        contextual_patterns=_p(),
        jobs=("occasion_social", "impulse_park", "bookmark_later"),
        blockers=("styling_occasion",),
    ),
    ThemeSpec(
        id="social_validation_review",
        category="blocker",
        label="Social validation / review-seeking",
        patterns=_p(
            r"does anyone have this",
            r"reviews? before (?:i )?buy",
            r"asking before i order",
            r"saw someone wearing",
            r"influencer wore",
            r"seen on instagram",
            r"is this good quality",
            r"worth buying\?",
            r"worth buying",
            r"is (?:it|this) worth buying",
            r"anyone tried this brand",
            r"not enough reviews",
            r"reviews? (?:are )?not enough",
        ),
        jobs=("shortlist_compare", "intent_blocked"),
        blockers=("review_volume_trust", "social_validation"),
    ),
    ThemeSpec(
        id="trust_quality_doubt",
        category="blocker",
        label="Trust / quality doubt",
        patterns=_p(
            r"quality issues?",
            r"fabric feels cheap",
            r"colour looks different|color looks different",
            r"read mixed reviews",
            r"scared of bad quality",
            r"fake reviews?",
            r"photos? vs real product",
            r"looks different (?:in|on) (?:the )?(?:pic|photo|person|video)",
            r"not like the (?:pic|photo)",
        ),
        contextual_patterns=_p(r"return experience"),
        jobs=("intent_blocked",),
        blockers=("fabric_quality", "photo_mismatch", "authenticity", "returns"),
        requires_save_context=True,
    ),
    ThemeSpec(
        id="comparison_shopping",
        category="blocker",
        label="Comparison shopping",
        patterns=_p(
            r"myntra vs ajio|ajio vs myntra|myntra or ajio",
            r"cheaper elsewhere",
            r"found same product on",
            r"comparing options",
            r"similar item",
            r"alternative to",
            r"which one should i buy",
            r"torn between",
            r"confused between",
        ),
        contextual_patterns=_p(
            r"\bvs\.?\b",
            r"\b(?:flipkart|amazon|ajio|nykaa|meesho)\b",
        ),
        jobs=("shortlist_compare",),
        blockers=("competitor_check",),
        requires_save_context=True,
    ),
    ThemeSpec(
        id="stock_availability",
        category="blocker",
        label="Stock / availability friction",
        patterns=_p(
            r"out of stock",
            r"sold out",
            r"size unavailable",
            r"back in stock",
            r"back in stock notify",
            r"notify (?:me )?when",
            r"wishlist item disappeared",
            r"removed from wishlist(?: automatically)?",
        ),
        jobs=("intent_blocked", "bookmark_later"),
        blockers=(),
        requires_save_context=True,
    ),
    ThemeSpec(
        id="bookmark_not_buying",
        category="blocker",
        label="Bookmarking-not-buying behavior",
        patterns=_p(
            r"forgot i (?:even )?saved",
            r"wishlist is (?:just )?(?:a )?graveyard",
            r"never actually buy",
            r"hoarding wishlist",
            r"100\+ items saved",
            r"just window shopping",
            r"add to wishlist.{0,40}(?:never|just looking|for later)",
            r"wishlist.{0,40}(?:never|graveyard|window shop)",
            r"wishlist crying",
        ),
        jobs=("bookmark_later", "impulse_park"),
        blockers=(),
    ),
    ThemeSpec(
        id="trigger_to_purchase",
        category="conversion",
        label="Trigger-to-purchase moment",
        patterns=_p(
            r"finally bought",
            r"took me months",
            r"glad i waited",
            r"impulse bought (?:it )?after",
            r"bought after seeing (?:it )?on sale",
            r"friend recommended",
            r"needed it for (?:an )?event",
            r"restocked so i grabbed",
            r"price dropped so i bought",
            r"ordered from (?:my )?wishlist",
            r"bought from wishlist",
        ),
        jobs=("bookmark_later", "wait_for_sale"),
        blockers=(),
    ),
    ThemeSpec(
        id="wishlist_ux_friction",
        category="ux",
        label="Wishlist UX / product friction",
        patterns=_p(
            r"buy all (?:my )?wishlist",
            r"wishlist.{0,40}filter",
            r"wishlist doesn'?t let me filter",
            r"wishlist synced(?: across devices)?",
            r"lost my wishlist",
            r"wishlist notification",
            r"no price alert.{0,30}wishlist",
            r"wishlist vs cart",
            r"double (?:tap|click) to wishlist",
            r"exploring wishlist",
        ),
        jobs=("bookmark_later",),
        blockers=("delivery_checkout_saved",),
    ),
    ThemeSpec(
        id="post_purchase_validation",
        category="validation",
        label="Post-purchase validation (overcame hesitation)",
        patterns=_p(
            r"so glad i finally bought",
            r"should'?ve bought sooner",
            r"wish i bought earlier",
            r"hesitated for so long but",
            r"no regrets buying",
        ),
        jobs=("intent_blocked",),
        blockers=(),
    ),
)

THEME_BY_ID = {spec.id: spec for spec in THEME_SPECS}
BLOCKER_THEME_IDS = frozenset(s.id for s in THEME_SPECS if s.category == "blocker")
CONVERSION_THEME_IDS = frozenset(s.id for s in THEME_SPECS if s.category == "conversion")
UX_THEME_IDS = frozenset(s.id for s in THEME_SPECS if s.category == "ux")
VALIDATION_THEME_IDS = frozenset(s.id for s in THEME_SPECS if s.category == "validation")
RELEVANCE_THEME_IDS = BLOCKER_THEME_IDS | CONVERSION_THEME_IDS | UX_THEME_IDS | VALIDATION_THEME_IDS

_COMPARISON_SHOPPING_INTENT = re.compile(
    r"confused between|torn between|which (?:one )?should i buy|comparing options|"
    r"myntra (?:vs\.?|or) (?:ajio|amazon)|ajio (?:vs\.?|or) myntra|cheaper elsewhere|"
    r"found same product on|similar item|alternative to",
    re.I,
)

_COMPARISON_NOISE = re.compile(
    r"\bdelivery\b|\bcancel(?:led|lation)|customer (?:service|care|support)|"
    r"worst (?:app|experience|shopping)|exchange process|refund|horrible delivery|"
    r"never try to order|waste(?:d)? my (?:important )?time",
    re.I,
)

_STOCK_DELIVERY_NOISE = re.compile(
    r"horrible delivery|customer (?:service|care|support)|delivery (?:was )?(?:delayed|late)|"
    r"never (?:try to )?order|worst (?:app|experience)|1-star experience|"
    r"contacted myntra customer support",
    re.I,
)

_STOCK_SAVE_SIGNAL = re.compile(
    r"wish\s*list|wishlisted|saved|shortlist|bookmark|add(?:ed)? to (?:wishlist|cart)|out of stock|sold out|"
    r"size unavailable|back in stock",
    re.I,
)

def has_save_or_compare_context(text: str) -> bool:
    return bool(_SAVED_OR_DELAY.search(text) or _COMPARE_CONTEXT.search(text))


def _theme_matches(spec: ThemeSpec, text: str) -> bool:
    body = (text or "").strip()
    if not body:
        return False
    strong = any(p.search(body) for p in spec.patterns)
    weak = any(p.search(body) for p in spec.contextual_patterns)
    if not strong and not weak:
        return False
    if spec.requires_save_context and not has_save_or_compare_context(body):
        if not strong:
            return False
    if spec.id == "trust_quality_doubt":
        if returns_blocks_saved_purchase(body) or fabric_quality_blocks_saved_purchase(body):
            return True
        if strong and has_save_or_compare_context(body):
            return True
        if weak and has_save_or_compare_context(body):
            return True
        return bool(strong and re.search(r"before (?:i )?(?:buy|order)|won'?t buy", body, re.I))
    if spec.id == "fit_size_uncertainty" and weak and not strong:
        return fit_blocks_saved_purchase(body) or has_save_or_compare_context(body)
    if spec.id == "comparison_shopping":
        has_intent = bool(_COMPARISON_SHOPPING_INTENT.search(body))
        if _COMPARISON_NOISE.search(body) and not has_intent:
            return False
        if weak and not strong and not has_save_or_compare_context(body) and not has_intent:
            return False
    if spec.id == "stock_availability":
        if _STOCK_DELIVERY_NOISE.search(body) and not _STOCK_SAVE_SIGNAL.search(body):
            return False
        if not _STOCK_SAVE_SIGNAL.search(body) and not has_save_or_compare_context(body):
            return False
    return True


def detect_wishlist_themes(text: str) -> tuple[str, ...]:
    out: list[str] = []
    for spec in THEME_SPECS:
        if _theme_matches(spec, text):
            out.append(spec.id)
    return tuple(out)


def theme_clues(themes: Iterable[str]) -> list[str]:
    return [f"theme:{theme_id}" for theme_id in themes]


def themes_for_jobs_blockers(themes: Iterable[str]) -> tuple[list[str], list[str]]:
    jobs: list[str] = []
    blockers: list[str] = []
    for theme_id in themes:
        spec = THEME_BY_ID.get(theme_id)
        if not spec:
            continue
        for job in spec.jobs:
            if job not in jobs:
                jobs.append(job)
        for blocker in spec.blockers:
            if blocker not in blockers:
                blockers.append(blocker)
    return jobs, blockers


def apply_theme_blockers(text: str, jobs: list[str], blockers: list[str]) -> tuple[list[str], list[str]]:
    """Merge theme-derived jobs/blockers with contextual gates for sensitive blockers."""
    themes = detect_wishlist_themes(text)
    t_jobs, t_blockers = themes_for_jobs_blockers(themes)
    jobs = list(jobs)
    blockers = list(blockers)
    for job in t_jobs:
        if job not in jobs:
            jobs.append(job)
    for blocker in t_blockers:
        if blocker in blockers:
            continue
        if blocker == "returns" and not returns_blocks_saved_purchase(text):
            continue
        if blocker in ("fit", "size_chart") and not fit_blocks_saved_purchase(text):
            continue
        if blocker == "fabric_quality" and not fabric_quality_blocks_saved_purchase(text):
            continue
        blockers.append(blocker)
    return jobs, blockers


def theme_labels(themes: Iterable[str]) -> list[str]:
    return [THEME_BY_ID[t].label for t in themes if t in THEME_BY_ID]
