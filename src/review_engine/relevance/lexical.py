"""Recall-oriented lexical gate for wishlist / postpone / compare language."""

from __future__ import annotations

import re
from dataclasses import dataclass

from review_engine.wishlist_context import fit_uncertainty_signal, returns_trust_signal
from review_engine.wishlist_themes import RELEVANCE_THEME_IDS, detect_wishlist_themes

KNOWN_TAGS = (
    "wishlist_language",
    "postpone",
    "compare",
    "fit_uncertainty",
    "price_wait",
    "external_validation",
    "returns_trust",
    "occasion",
    "checkout_saved",
    "save_behavior_theme",
)

BORDERLINE_KEEP_TAGS = frozenset({"price_wait", "compare", "postpone"})
PRECISION_TAGS = frozenset(
    {
        "wishlist_language",
        "postpone",
        "compare",
        "fit_uncertainty",
        "price_wait",
        "external_validation",
        "occasion",
        "checkout_saved",
        "save_behavior_theme",
    }
)

_TAG_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "wishlist_language": (
        re.compile(r"wish\s*list", re.I),
        re.compile(r"\bshortlist", re.I),
        re.compile(r"save[d]?\s+for\s+later", re.I),
        re.compile(r"\badded to (my )?wish", re.I),
        re.compile(r"\bbookmark", re.I),
        re.compile(r"wishlist(?:ed|ing)?\b", re.I),
        re.compile(r"from (?:my )?wishlist", re.I),
        re.compile(r"(?:to|on|in) (?:my )?wishlist", re.I),
        re.compile(r"wishlist.{0,40}(?:price|buy|purchase|order|item)", re.I),
        re.compile(r"(?:price|buy|purchase|order).{0,40}wishlist", re.I),
        re.compile(r"saved items?", re.I),
        re.compile(r"exploring wishlist", re.I),
    ),
    "postpone": (
        re.compile(r"\bpostpon", re.I),
        re.compile(r"\blater\b", re.I),
        re.compile(r"waiting for salary|salary (day|aaye|aata)", re.I),
        re.compile(r"next month|baad mein|baad me\b", re.I),
        re.compile(r"won't buy until|will buy after|not ordered yet", re.I),
    ),
    "compare": (
        re.compile(r"\bvs\.?\b|\bversus\b", re.I),
        re.compile(r"confused between|between these two", re.I),
        re.compile(r"which (one|is better)|myntra or ajio|ajio or myntra", re.I),
        re.compile(r"shortlist(ed)? (these|two|items)", re.I),
    ),
    "price_wait": (
        re.compile(r"\beors\b|end of reason", re.I),
        re.compile(r"wait(ing)? for (the )?sale|until (the )?sale|sale (mein|me) (lunga|lenge)", re.I),
        re.compile(r"price drop|discount wait|when (it )?goes on sale", re.I),
    ),
    "external_validation": (
        re.compile(r"\bhaul\b", re.I),
        re.compile(r"looks different (in|on) (the )?(video|pic|photo|person)", re.I),
        re.compile(r"reviews? (are )?not enough|not enough reviews", re.I),
        re.compile(r"youtube|instagram haul", re.I),
    ),
    "occasion": (
        re.compile(r"\bwedding\b|shaadi", re.I),
        re.compile(r"office look|office wear|work wear", re.I),
    ),
    "checkout_saved": (
        re.compile(r"(wishlist|saved).{0,40}(checkout|payment|pay now)", re.I),
        re.compile(r"(checkout|payment).{0,40}(wishlist|saved item)", re.I),
    ),
}

_GATE_EXTRA = (
    re.compile(r"\bsale\b", re.I),
    re.compile(r"\bsaved\b", re.I),
    re.compile(r"try (it )?in store|store try[- ]?on", re.I),
)

_NEGATIVE_ONLY = (
    re.compile(r"\botp\b|\blogin\b|\bsign in\b|\bpassword\b", re.I),
    re.compile(r"\bcrash|\bforce close|\bkeeps stopping", re.I),
    re.compile(r"\bdelivery\b|\bcourier\b|\botp\b", re.I),
)

_SPAM = re.compile(r"https?://|whatsapp|\btelegram\b", re.I)


@dataclass(frozen=True)
class LexicalResult:
    gated: bool
    tags: tuple[str, ...]
    gate_reason: str


def lexical_gate(text: str) -> LexicalResult:
    body = (text or "").strip()
    if len(body) < 12 or len(body.split()) <= 1:
        return LexicalResult(False, (), "too_short")
    if _SPAM.search(body) and len(body.split()) < 8:
        return LexicalResult(False, (), "spam")

    tags = [name for name, patterns in _TAG_PATTERNS.items() if any(p.search(body) for p in patterns)]
    if fit_uncertainty_signal(body):
        tags.append("fit_uncertainty")
    if returns_trust_signal(body):
        tags.append("returns_trust")
    themes = detect_wishlist_themes(body)
    if any(t in RELEVANCE_THEME_IDS for t in themes):
        tags.append("save_behavior_theme")
    extra_gate = any(p.search(body) for p in _GATE_EXTRA)
    negative = any(p.search(body) for p in _NEGATIVE_ONLY)

    if tags or extra_gate:
        return LexicalResult(True, tuple(tags), "positive_or_borderline")
    if negative:
        return LexicalResult(False, (), "negative_class")
    return LexicalResult(False, (), "no_signal")


def heuristic_score(tags: tuple[str, ...], gated: bool) -> float:
    if not gated:
        return 0.0
    strong = [t for t in tags if t in PRECISION_TAGS]
    if "wishlist_language" in tags:
        return 0.86
    if strong:
        return min(0.55 + 0.12 * len(strong), 0.92)
    # gated only on broad words like "sale" / "saved"
    return 0.28
