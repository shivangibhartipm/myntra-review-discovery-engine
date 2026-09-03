"""Lexical fallback for jobs/blockers. Obvious cases: eors, wishlist, size chart."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from review_engine.extract.taxonomy import BLOCKERS, JOBS
from review_engine.wishlist_context import (
    authenticity_blocks_saved_purchase,
    fabric_quality_blocks_saved_purchase,
    fit_blocks_saved_purchase,
    returns_blocks_saved_purchase,
    size_chart_blocks_saved_purchase,
)
from review_engine.wishlist_themes import apply_theme_blockers as _apply_theme_blockers
from review_engine.wishlist_themes import detect_wishlist_themes, theme_clues

_JOB_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "wait_for_sale": (
        re.compile(r"\beors\b|end of reason", re.I),
        re.compile(r"wait(ing)? for (the )?sale|until (the )?sale", re.I),
        re.compile(r"price drop|when (it )?goes on sale|sale (mein|me) (lunga|lenge)", re.I),
    ),
    "bookmark_later": (
        re.compile(r"save[d]?\s+for\s+later|when i have money|salary", re.I),
        re.compile(r"baad mein|baad me\b|next month|\bpostpon", re.I),
        re.compile(r"wish\s*list", re.I),
    ),
    "shortlist_compare": (
        re.compile(r"confused between|between these two|which (one|is better)", re.I),
        re.compile(r"\bvs\.?\b|\bversus\b|myntra or ajio|shortlist", re.I),
    ),
    "intent_blocked": (
        re.compile(r"(love|like|want).{0,40}but.{0,40}(size|return|fake|price|fit)", re.I),
        re.compile(r"won't buy until|will not buy until|size chart", re.I),
        re.compile(r"(return policy|fake|authenticit).{0,40}(worri|scar|risk|buy|order)", re.I),
    ),
    "occasion_social": (
        re.compile(r"\bwedding\b|shaadi|office look|office wear|will this look good", re.I),
    ),
    "impulse_park": (
        re.compile(r"liked the (pic|picture|photo)|cute pic|saved because of (the )?pic", re.I),
    ),
}

_BLOCKER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "photo_mismatch": (
        re.compile(r"looks different|photo mismatch|not like the (pic|photo)", re.I),
    ),
    "fabric_quality": (re.compile(r"thin material", re.I),),
    "price": (re.compile(r"\bexpensive\b|\bcostly\b|\bprice\b|overpriced", re.I),),
    "sale_timing": (re.compile(r"\beors\b|wait(ing)? for (the )?sale|sale timing", re.I),),
    "review_volume_trust": (re.compile(r"not enough reviews|reviews? (are )?not enough", re.I),),
    "delivery_checkout_saved": (
        re.compile(r"(wishlist|saved).{0,40}(checkout|payment)", re.I),
        re.compile(r"(checkout|payment).{0,40}(wishlist|saved)", re.I),
    ),
    "styling_occasion": (re.compile(r"office look|wedding|styling", re.I),),
    "social_validation": (re.compile(r"will this look good|ask(ing)? (my )?friend", re.I),),
    "competitor_check": (re.compile(r"\bajio\b|\bnykaa\b|amazon fashion|\bmeesho\b", re.I),),
}

_POSTPONE_YES = re.compile(
    r"salary|next month|baad mein|postpon|wait(ing)? for (the )?sale|\beors\b|until (the )?sale|later",
    re.I,
)
_OUTSIDE = re.compile(r"youtube|\bhaul\b|\bajio\b|amazon|nykaa|instagram|google reviews", re.I)
_GENDER = re.compile(r"\bi(?:'m| am) a (woman|man|girl|guy)\b", re.I)


@dataclass
class LexicalClaim:
    jobs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    postponement_beyond_30d: str = "unknown"
    outside_myntra_info_seeking: bool = False
    segment_clues: list[str] = field(default_factory=list)
    evidence_span: str = ""
    confidence: float = 0.45


def extract_lexical(text: str, *, source: str = "", category: str = "") -> LexicalClaim:
    body = text or ""
    jobs = [name for name, pats in _JOB_PATTERNS.items() if any(p.search(body) for p in pats)]
    blockers = [name for name, pats in _BLOCKER_PATTERNS.items() if any(p.search(body) for p in pats)]
    if returns_blocks_saved_purchase(body):
        blockers.append("returns")
    if authenticity_blocks_saved_purchase(body):
        blockers.append("authenticity")
    if fit_blocks_saved_purchase(body):
        blockers.append("fit")
    if size_chart_blocks_saved_purchase(body):
        blockers.append("size_chart")
    if fabric_quality_blocks_saved_purchase(body):
        blockers.append("fabric_quality")
    jobs, blockers = _apply_theme_blockers(body, jobs, blockers)
    themes = detect_wishlist_themes(body)
    jobs = [j for j in jobs if j in JOBS]
    blockers = [b for b in blockers if b in BLOCKERS]
    # Do not treat "size" on a sale-wait-only sentence as intent_blocked unless blocked language exists.
    if "intent_blocked" not in jobs and "size_chart" in blockers:
        jobs.append("intent_blocked")
    postpone = "yes" if _POSTPONE_YES.search(body) else "unknown"
    clues = []
    if source == "app_store":
        clues.append("platform:ios")
    elif source == "play":
        clues.append("platform:android")
    if category:
        clues.append(f"category:{category}")
    clues.extend(theme_clues(themes))
    if re.search(r"\bwedding\b|shaadi", body, re.I):
        clues.append("occasion:wedding")
    if re.search(r"office look|office wear|workwear|formals|for office", body, re.I):
        clues.append("occasion:office")
    if re.search(r"diwali|festive|navratri|eid|puja|holi|festival", body, re.I):
        clues.append("occasion:festive")
    if re.search(r"gen\s*z|gen-z|college|campus|hostel|student|university|teen", body, re.I):
        clues.append("demo:genz_youth")
    if re.search(r"again|always order|regular customer|every time|loyal|repeat order|ordered many", body, re.I):
        clues.append("lifecycle:repeat")
    if re.search(r"first order|first time|new to myntra|first purchase", body, re.I):
        clues.append("lifecycle:first_time")
    if re.search(r"expensive|salary|when i have money|price drop|budget|paycheck", body, re.I):
        clues.append("price_sensitive")
    if re.search(r"for my (kid|child|son|daughter)|kids wear|baby", body, re.I):
        clues.append("demo:parent")
    gender = _GENDER.search(body)
    if gender:
        clues.append(f"gender:{gender.group(1).lower()}")
    span = _best_span(body, jobs, blockers)
    if not jobs and not blockers:
        jobs = ["unknown"]
    return LexicalClaim(
        jobs=_uniq(jobs),
        blockers=_uniq(blockers),
        postponement_beyond_30d=postpone,
        outside_myntra_info_seeking=bool(_OUTSIDE.search(body)),
        segment_clues=_uniq(clues),
        evidence_span=span,
        confidence=0.7 if jobs != ["unknown"] else 0.3,
    )


def _uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _best_span(text: str, jobs: list[str], blockers: list[str]) -> str:
    needles = []
    if "wait_for_sale" in jobs:
        needles += ["EORS", "eors", "sale", "price drop"]
    if "bookmark_later" in jobs:
        needles += ["wishlist", "wish list", "later", "salary"]
    if "shortlist_compare" in jobs:
        needles += ["confused between", "shortlist", "vs", "Ajio"]
    if "intent_blocked" in jobs or "size_chart" in blockers:
        needles += ["size chart", "size", "fake"]
    if "occasion_social" in jobs:
        needles += ["wedding", "office"]
    if "impulse_park" in jobs:
        needles += ["pic", "photo"]
    for needle in needles:
        idx = text.lower().find(needle.lower())
        if idx >= 0:
            return text[idx : idx + len(needle)]
    return text[:80] if text else ""
