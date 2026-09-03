"""Scan corpus text for wishlist save habits, frequency, and conversion signals."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from review_engine.wishlist_themes import THEME_BY_ID, detect_wishlist_themes

_WISHLIST_WORD = re.compile(
    r"wish\s*list|wishlisted|saved for later|save[d]?\s+for|bookmark|shortlist|"
    r"from (?:my )?wishlist|(?:to|on|in) (?:my )?wishlist|added to wish|"
    r"wishlist item|saved item|items? i saved|my saves|exploring wishlist",
    re.I,
)

_FREQ_ADD = re.compile(
    r"every time.{0,50}(?:wish\s*list|save|add)|"
    r"(?:often|always|frequently|daily|regularly).{0,40}(?:wish\s*list|save|add to)",
    re.I,
)

_FREQ_BUY = re.compile(
    r"(?:buy|purchase|order|shop).{0,60}from (?:my )?wishlist|"
    r"wishlist.{0,60}(?:buy|purchase|order|convert|checkout)|"
    r"(?:never|rarely|seldom|hardly).{0,40}(?:buy|bought|purchase).{0,40}wishlist|"
    r"wishlist.{0,40}(?:never|rarely|seldom).{0,40}(?:buy|bought|purchase)",
    re.I,
)

_ADD_REASON = (
    ("wait_for_sale", re.compile(r"wait(ing)? for (?:the )?sale|\beors\b|price drop|salary|buy later", re.I)),
    ("compare", re.compile(r"confused between|shortlist|which is better|myntra or ajio|\bvs\b", re.I)),
    ("price_track", re.compile(r"price (?:increase|drop|alert|higher)|expensive", re.I)),
    ("fit_uncertainty", re.compile(r"size chart|don't know (?:my )?size|not sure (?:about )?(?:the )?size", re.I)),
    ("haul_photo", re.compile(r"haul|looks different|photo|pic", re.I)),
    ("occasion", re.compile(r"wedding|office|festive|occasion", re.I)),
    ("impulse_park", re.compile(r"liked the (?:pic|photo)|cute|bookmark", re.I)),
)


@dataclass
class WishlistSignalReport:
    n_corpus: int = 0
    n_relevant: int = 0
    n_wishlist_language: int = 0
    n_freq_add: int = 0
    n_freq_buy: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    add_reasons: dict[str, int] = field(default_factory=dict)
    freq_add_samples: list[str] = field(default_factory=list)
    freq_buy_samples: list[str] = field(default_factory=list)
    wishlist_samples: list[str] = field(default_factory=list)
    behavior_themes: dict[str, int] = field(default_factory=dict)
    theme_samples: dict[str, list[str]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_corpus": self.n_corpus,
            "n_relevant": self.n_relevant,
            "n_wishlist_language": self.n_wishlist_language,
            "n_freq_add": self.n_freq_add,
            "n_freq_buy": self.n_freq_buy,
            "by_source": self.by_source,
            "add_reasons": self.add_reasons,
            "behavior_themes": self.behavior_themes,
            "theme_samples": {k: v[:3] for k, v in self.theme_samples.items()},
            "freq_add_samples": self.freq_add_samples[:5],
            "freq_buy_samples": self.freq_buy_samples[:5],
            "wishlist_samples": self.wishlist_samples[:8],
        }


def analyze_wishlist_signals(
    rows: Iterable[Mapping[str, Any]],
    *,
    relevant_only: bool = False,
) -> WishlistSignalReport:
    report = WishlistSignalReport()
    for row in rows:
        text = str(row.get("text") or "")
        source = str(row.get("source") or "unknown")
        is_rel = bool(row.get("is_relevant"))
        if relevant_only and not is_rel:
            continue
        report.n_corpus += 1
        if is_rel:
            report.n_relevant += 1
        themes = detect_wishlist_themes(text)
        for theme_id in themes:
            spec = THEME_BY_ID.get(theme_id)
            if not spec:
                continue
            report.behavior_themes[theme_id] = report.behavior_themes.get(theme_id, 0) + 1
            samples = report.theme_samples.setdefault(theme_id, [])
            if len(samples) < 3:
                samples.append(_clip(text))
        if not _WISHLIST_WORD.search(text):
            continue
        report.n_wishlist_language += 1
        report.by_source[source] = report.by_source.get(source, 0) + 1
        snippet = _clip(text)
        if len(report.wishlist_samples) < 8:
            report.wishlist_samples.append(snippet)
        for reason, pattern in _ADD_REASON:
            if pattern.search(text):
                report.add_reasons[reason] = report.add_reasons.get(reason, 0) + 1
        if _FREQ_ADD.search(text):
            report.n_freq_add += 1
            if len(report.freq_add_samples) < 5:
                report.freq_add_samples.append(snippet)
        if _FREQ_BUY.search(text):
            report.n_freq_buy += 1
            if len(report.freq_buy_samples) < 5:
                report.freq_buy_samples.append(snippet)
    return report


def merge_job_reasons(job_weights: dict[str, float], signal_reasons: dict[str, int]) -> list[tuple[str, str]]:
    """Combine ranked opportunity jobs with explicit wishlist-comment reason tags."""
    labels = {
        "wait_for_sale": "wait for a sale, salary, or price drop",
        "bookmark_later": "park items to buy later on purpose",
        "shortlist_compare": "compare or shortlist before choosing",
        "compare": "compare options before buying",
        "price_track": "track price changes on saved items",
        "fit_uncertainty": "unclear size or fit before ordering",
        "haul_photo": "check hauls or photos before committing",
        "occasion": "hold looks for an occasion",
        "impulse_park": "save something that caught their eye",
        "intent_blocked": "want the item but a blocker stops checkout",
        "occasion_social": "wait for occasion or social confidence",
    }
    scores: Counter[str] = Counter()
    for key, weight in job_weights.items():
        if weight and key != "unknown":
            scores[key] += float(weight)
    for key, count in signal_reasons.items():
        scores[key] += count * 0.15
    ordered = scores.most_common()
    return [(key, labels.get(key, key.replace("_", " "))) for key, _ in ordered if key != "unknown"]


def _clip(text: str, limit: int = 200) -> str:
    body = re.sub(r"\s+", " ", (text or "").strip())
    return body if len(body) <= limit else body[: limit - 1] + "…"
