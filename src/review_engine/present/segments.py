"""Demographic and lifestyle shopper segments for discovery answers.

Segments are inferred only from explicit language in comments (college/Gen Z cues,
repeat-order talk, wedding/office/festive occasions, salary/budget). We do not invent
demographics from platform or app metadata.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]

# (id, label, how behavior differs, regex)
_SEGMENT_DEFS: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    (
        "genz_youth",
        "Gen Z / young shoppers",
        "College or Gen Z cues show up with hesitation — often about price, photos, or first purchases.",
        re.compile(
            r"gen\s*z|gen-z|zoomer|college|campus|hostel|student|university|teen(?:ager)?s?|"
            r"first job|hostel life",
            re.I,
        ),
    ),
    (
        "repeat_shoppers",
        "Repeat / loyal shoppers",
        "They order on Myntra regularly but still save items — loyalty does not mean fast conversion.",
        re.compile(
            r"\bagain\b|always order|regular customer|every time|loyal|repeat order|"
            r"ordered many|myntra (is|has been) my|been using myntra|long time (user|customer)",
            re.I,
        ),
    ),
    (
        "first_time",
        "First-time shoppers",
        "New buyers save while learning trust, fit, and whether products look like the photos.",
        re.compile(r"first order|first time|new to myntra|first purchase|never ordered", re.I),
    ),
    (
        "occasion_wedding",
        "Wedding / occasion shoppers",
        "They save wedding or family-event outfits and wait until the look feels right for the day.",
        re.compile(r"wedding|shaadi|bridal|sangeet|reception|haldi", re.I),
    ),
    (
        "occasion_office",
        "Office / workwear shoppers",
        "They save office looks and hold off until the outfit feels professional and fits right.",
        re.compile(r"office look|office wear|workwear|formals|work outfit|for office", re.I),
    ),
    (
        "occasion_festive",
        "Festive shoppers",
        "They save festive outfits and may wait for the right sale or styling confidence before buying.",
        re.compile(r"diwali|festive|navratri|eid|puja|holi|festive season|festival", re.I),
    ),
    (
        "budget_salary",
        "Budget / salary-cycle shoppers",
        "They save until salary or budget allows — timing drives the delay, not lack of desire.",
        re.compile(
            r"salary|paycheck|when i have money|budget|month end|next month|"
            r"baad mein|baad me\b|after i get paid",
            re.I,
        ),
    ),
    (
        "deal_hunters",
        "Deal hunters / sale shoppers",
        "They save items and wait for EORS or a price drop — the list works like a personal sale alert.",
        re.compile(r"\beors\b|end of reason|wait(ing)? for (the )?sale|price drop|until (the )?sale", re.I),
    ),
    (
        "parents",
        "Parents buying for kids",
        "They save kids’ or family items and often need extra fit and trust before buying.",
        re.compile(r"for my (kid|child|son|daughter)|kids wear|kidswear|\bbaby\b|for my children", re.I),
    ),
)

_RARE_IDS = {
    "genz_youth",
    "occasion_wedding",
    "occasion_office",
    "occasion_festive",
    "parents",
}


def compute_demographic_segments(
    texts: Iterable[str],
    *,
    min_share: float = 0.005,
    min_n: int = 1,
) -> list[dict[str, Any]]:
    docs = [t for t in texts if (t or "").strip()]
    n = len(docs)
    if n <= 0:
        return []
    out: list[dict[str, Any]] = []
    for sid, label, diff, pattern in _SEGMENT_DEFS:
        hits = sum(1 for t in docs if pattern.search(t))
        share = hits / n
        if hits < min_n or share < min_share:
            continue
        out.append(
            {
                "id": sid,
                "label": label,
                "diff": diff,
                "n": hits,
                "share": round(share, 4),
                "opportunity_ids": [],
            }
        )
    out.sort(key=lambda s: (-float(s["share"]), s["label"]))
    return out


def _load_texts(path: Path, *, relevant_only: bool) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        if relevant_only:
            cur.execute(
                """
                SELECT r.text
                FROM raw_documents r
                JOIN document_enrichment e ON e.doc_id = r.doc_id
                WHERE e.is_relevant = 1 AND r.text IS NOT NULL AND TRIM(r.text) != ''
                """
            )
        else:
            cur.execute("SELECT text FROM raw_documents WHERE text IS NOT NULL AND TRIM(text) != ''")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def demographic_segments_from_db(
    db_path: Path | None = None,
    *,
    relevant_only: bool = True,
) -> list[dict[str, Any]]:
    path = Path(db_path) if db_path else ROOT / "data" / "engine.db"
    if not path.exists():
        return []
    texts = _load_texts(path, relevant_only=relevant_only)
    segments = compute_demographic_segments(texts, min_share=0.005, min_n=1)
    if relevant_only:
        # Add rare Gen Z / occasion / parent cues from the wider corpus when missing
        broader = compute_demographic_segments(
            _load_texts(path, relevant_only=False),
            min_share=0.0005,
            min_n=2,
        )
        seen = {s["id"] for s in segments}
        for row in broader:
            if row["id"] in _RARE_IDS and row["id"] not in seen:
                row = dict(row)
                row["diff"] = (
                    str(row["diff"])
                    + " Explicit cues are thin in wishlist-relevant comments; this share is from the wider corpus."
                )
                segments.append(row)
                seen.add(row["id"])
        segments.sort(key=lambda s: (-float(s["share"]), s["label"]))
    return segments


def attach_opportunity_ids(
    segments: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Link segments to related opportunity themes when jobs/blockers align."""
    job_map = {
        "deal_hunters": ("wait_for_sale",),
        "budget_salary": ("bookmark_later",),
        "occasion_wedding": ("occasion_social",),
        "occasion_office": ("occasion_social",),
        "occasion_festive": ("occasion_social",),
        "genz_youth": ("impulse_park", "bookmark_later"),
    }
    blocker_map = {
        "deal_hunters": ("sale_timing", "price"),
        "budget_salary": ("price",),
        "occasion_wedding": ("styling_occasion", "social_validation"),
        "occasion_office": ("styling_occasion",),
        "occasion_festive": ("styling_occasion",),
    }
    out = []
    for seg in segments:
        ids: list[str] = []
        for row in opportunities:
            oid = str(row.get("opportunity_id") or "")
            jmix = row.get("job_mix") if isinstance(row.get("job_mix"), dict) else {}
            bmix = row.get("blocker_mix") if isinstance(row.get("blocker_mix"), dict) else {}
            jobs = job_map.get(seg["id"], ())
            blockers = blocker_map.get(seg["id"], ())
            if any(float(jmix.get(j) or 0) > 0 for j in jobs) or any(
                float(bmix.get(b) or 0) > 0 for b in blockers
            ):
                if oid:
                    ids.append(oid)
        row = dict(seg)
        row["opportunity_ids"] = list(dict.fromkeys(ids))[:3]
        out.append(row)
    return out
