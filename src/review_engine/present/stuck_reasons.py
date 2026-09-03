"""Aggregate stuck-reason theme tags for opportunities and corpus health."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Iterable, Mapping

from review_engine.wishlist_themes import (
    BLOCKER_THEME_IDS,
    THEME_BY_ID,
    THEME_SPECS,
    detect_wishlist_themes,
    theme_labels,
)

_CATEGORY_ORDER = ("blocker", "ux", "conversion", "validation")


def _parse_clues(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("["):
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    return [str(x) for x in data if x]
            except json.JSONDecodeError:
                pass
        return [text] if text else []
    return []


def themes_for_member(
    doc_id: str,
    *,
    documents: Mapping[str, Mapping[str, Any]] | None,
    enrichments: Mapping[str, Mapping[str, Any]] | None,
) -> set[str]:
    themes: set[str] = set()
    enr = (enrichments or {}).get(str(doc_id)) or {}
    for clue in _parse_clues(enr.get("segment_clues")):
        if clue.startswith("theme:"):
            themes.add(clue[6:])
    doc = (documents or {}).get(str(doc_id)) or {}
    text = str(doc.get("text") or "")
    if text:
        themes.update(detect_wishlist_themes(text))
    return themes


def stuck_reason_mix(
    member_doc_ids: Iterable[str],
    *,
    documents: Mapping[str, Mapping[str, Any]] | None = None,
    enrichments: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, float]:
    counts: Counter[str] = Counter()
    members = [str(doc_id) for doc_id in member_doc_ids]
    for doc_id in members:
        for theme_id in themes_for_member(doc_id, documents=documents, enrichments=enrichments):
            if theme_id in THEME_BY_ID:
                counts[theme_id] += 1
    n = max(1, len(members))
    return {k: round(v / n, 4) for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))}


def top_stuck_reason_labels(mix: Mapping[str, float], *, limit: int = 4) -> list[str]:
    ordered = sorted(mix.items(), key=lambda kv: (-kv[1], kv[0]))
    labels: list[str] = []
    for theme_id, share in ordered[:limit]:
        if share <= 0:
            continue
        spec = THEME_BY_ID.get(theme_id)
        if spec:
            labels.append(spec.label)
    return labels


def stuck_reason_catalog(
    rows: Iterable[Mapping[str, Any]],
    *,
    relevant_only: bool = True,
) -> list[dict[str, Any]]:
    """Corpus-wide stuck-reason counts from document text."""
    counts: Counter[str] = Counter()
    n_docs = 0
    for row in rows:
        if relevant_only and not row.get("is_relevant"):
            continue
        text = str(row.get("text") or "")
        if not text:
            continue
        n_docs += 1
        for theme_id in detect_wishlist_themes(text):
            counts[theme_id] += 1

    catalog: list[dict[str, Any]] = []
    for spec in THEME_SPECS:
        count = counts.get(spec.id, 0)
        catalog.append(
            {
                "id": spec.id,
                "label": spec.label,
                "category": spec.category,
                "count": count,
                "share": round(count / n_docs, 4) if n_docs else 0.0,
                "is_blocker": spec.id in BLOCKER_THEME_IDS,
            }
        )
    catalog.sort(
        key=lambda row: (
            -row["count"],
            _CATEGORY_ORDER.index(row["category"]) if row["category"] in _CATEGORY_ORDER else 9,
            row["label"],
        )
    )
    return catalog


def catalog_entry_labels(catalog: list[dict[str, Any]], *, limit: int = 6) -> list[str]:
    return [str(row["label"]) for row in catalog if row.get("count", 0) > 0][:limit]
