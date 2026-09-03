from __future__ import annotations

import json
from typing import Any, Mapping

from review_engine.pii import contains_pii, redact_text
from review_engine.present.levers import suggested_lever
from review_engine.present.plain import opportunity_plain
from review_engine.present.quote_relevance import (
    _is_displayable_quote,
    extract_relevant_snippet,
    filter_quotes_for_opportunity,
    fill_topic_quotes,
    polish_quote,
)
from review_engine.present.stuck_reasons import stuck_reason_mix, top_stuck_reason_labels
from review_engine.present.sources import is_board_source


JSON_KEYS = (
    "member_doc_ids",
    "representative_doc_ids",
    "job_mix",
    "blocker_mix",
    "source_mix",
    "quotes",
    "intent_vs_bookmark",
    "segment_slices",
)


def maybe_json(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in "[{":
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
        return value
    return value


def row_to_dict(row: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(row, dict):
        data = dict(row)
    else:
        data = {k: row[k] for k in row.keys()}
    for key in JSON_KEYS:
        if key in data:
            data[key] = maybe_json(data[key])
    data["single_source_warning"] = bool(data.get("single_source_warning"))
    return data


def _mix_keys(mix: Any) -> list[str]:
    if isinstance(mix, dict):
        return [k for k, v in mix.items() if v]
    if isinstance(mix, list):
        return [str(x) for x in mix]
    return []


def sanitize_quotes(
    quotes: Any,
    *,
    documents: Mapping[str, Mapping[str, Any]] | None = None,
    enrichments: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for raw in quotes or []:
        if not isinstance(raw, dict):
            continue
        doc_id = str(raw.get("doc_id") or "")
        quote = redact_text(str(raw.get("quote") or ""))
        source = str(raw.get("source") or "")
        observed_at = str(raw.get("observed_at") or "")
        doc = (documents or {}).get(doc_id)
        enr = (enrichments or {}).get(doc_id)
        text = redact_text(str(doc["text"])) if doc and doc.get("text") else ""
        if doc and not source:
            source = str(doc["source"] or "")
        if doc and not observed_at:
            observed_at = str(doc["observed_at"] or "")
        if not is_board_source(source):
            continue
        if quote and text and quote not in text:
            span = ""
            if enr and enr.get("evidence_span"):
                span = redact_text(str(enr["evidence_span"]))
            if span and span in text:
                quote = polish_quote(span, text)
            else:
                quote = extract_relevant_snippet(text) or polish_quote(text, text)
        elif quote and text:
            quote = polish_quote(quote, text)
        if not quote and text:
            quote = extract_relevant_snippet(text) or polish_quote(text, text)
        if contains_pii(quote):
            continue
        if not quote or not _is_displayable_quote(quote):
            continue
        out.append(
            {
                "doc_id": doc_id,
                "source": source,
                "observed_at": observed_at,
                "quote": quote,
            }
        )
    return out


def _member_doc_ids(
    raw: Mapping[str, Any],
    *,
    documents: Mapping[str, Mapping[str, Any]] | None,
) -> list[str]:
    kept: list[str] = []
    for doc_id in raw.get("member_doc_ids") or []:
        doc = (documents or {}).get(str(doc_id))
        if doc and not is_board_source(str(doc.get("source") or "")):
            continue
        kept.append(str(doc_id))
    return kept


def _source_mix_from_members(
    member_doc_ids: list[str],
    *,
    documents: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, float]:
    counts: dict[str, int] = {}
    for doc_id in member_doc_ids:
        doc = (documents or {}).get(str(doc_id))
        if not doc:
            continue
        source = str(doc.get("source") or "")
        if not is_board_source(source):
            continue
        counts[source] = counts.get(source, 0) + 1
    n = max(1, len(member_doc_ids))
    return {k: round(v / n, 4) for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))}


def board_row(
    raw: Mapping[str, Any],
    *,
    documents: Mapping[str, Mapping[str, Any]] | None = None,
    enrichments: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    job_mix = raw.get("job_mix") if isinstance(raw.get("job_mix"), dict) else {}
    blocker_mix = raw.get("blocker_mix") if isinstance(raw.get("blocker_mix"), dict) else {}
    member_doc_ids = _member_doc_ids(raw, documents=documents)
    source_mix = _source_mix_from_members(member_doc_ids, documents=documents)
    quotes = sanitize_quotes(
        raw.get("quotes") or [],
        documents=documents,
        enrichments=enrichments,
    )
    quotes = filter_quotes_for_opportunity(
        quotes,
        jobs=_mix_keys(job_mix),
        blockers=_mix_keys(blocker_mix),
        job_mix=job_mix,
        blocker_mix=blocker_mix,
        documents=documents,
        enrichments=enrichments,
    )
    quotes = fill_topic_quotes(
        quotes,
        member_doc_ids=member_doc_ids,
        jobs=_mix_keys(job_mix),
        blockers=_mix_keys(blocker_mix),
        job_mix=job_mix,
        blocker_mix=blocker_mix,
        documents=documents,
        enrichments=enrichments,
    )
    reason_mix = stuck_reason_mix(
        member_doc_ids,
        documents=documents,
        enrichments=enrichments,
    )
    stuck_reasons = top_stuck_reason_labels(reason_mix)
    layers: dict[str, int] = {}
    categories: dict[str, int] = {}
    for doc_id in member_doc_ids:
        doc = (documents or {}).get(str(doc_id))
        if not doc:
            continue
        if not is_board_source(str(doc.get("source") or "")):
            continue
        layer = str(doc.get("corpus_layer") or "unspecified")
        layers[layer] = layers.get(layer, 0) + 1
        cat = doc.get("product_or_category")
        if cat:
            categories[str(cat)] = categories.get(str(cat), 0) + 1
    n_members = max(1, len(member_doc_ids) or 1)
    corpus_layer_mix = {k: round(v / n_members, 4) for k, v in sorted(layers.items(), key=lambda kv: (-kv[1], kv[0]))}
    sources = _mix_keys(source_mix)
    return {
        "opportunity_id": raw.get("opportunity_id") or raw.get("id"),
        "problem_one_liner": raw.get("problem_one_liner") or "",
        "member_n": len(member_doc_ids),
        "rank_90d": raw.get("rank_90d"),
        "rank_12m": raw.get("rank_12m"),
        "volume_rank": raw.get("volume_rank"),
        "rank_score": raw.get("rank_score"),
        "rank_score_90d": raw.get("rank_score_90d"),
        "rank_score_12m": raw.get("rank_score_12m"),
        "metric_relevance": raw.get("metric_relevance"),
        "prevalence_relevant": raw.get("prevalence_relevant"),
        "prevalence_unfiltered": raw.get("prevalence_unfiltered"),
        "postponement_rate": raw.get("postponement_rate"),
        "recency_90d_share": raw.get("recency_90d_share"),
        "actionability": raw.get("actionability"),
        "multi_source_support": raw.get("multi_source_support"),
        "delay_mechanism": raw.get("delay_mechanism") or "",
        "comparison_notes": _plain_comparison(str(raw.get("comparison_notes") or "")),
        "job_mix": job_mix,
        "blocker_mix": blocker_mix,
        "source_mix": source_mix,
        "jobs": _mix_keys(job_mix),
        "blockers": _mix_keys(blocker_mix),
        "sources": sources,
        "intent_vs_bookmark": raw.get("intent_vs_bookmark") if isinstance(raw.get("intent_vs_bookmark"), dict) else {},
        "segment_slices": raw.get("segment_slices") if isinstance(raw.get("segment_slices"), list) else [],
        "corpus_layer_mix": corpus_layer_mix,
        "categories": sorted(categories, key=lambda k: (-categories[k], k)),
        "single_source_warning": len(sources) < 2,
        "suggested_lever": suggested_lever(job_mix, blocker_mix),
        "plain": opportunity_plain(
            {
                "metric_relevance": raw.get("metric_relevance"),
                "prevalence_relevant": raw.get("prevalence_relevant"),
                "postponement_rate": raw.get("postponement_rate"),
                "job_mix": job_mix,
                "blocker_mix": blocker_mix,
            }
        ),
        "quotes": quotes,
        "stuck_reason_mix": reason_mix,
        "stuck_reasons": stuck_reasons,
        "member_doc_ids": member_doc_ids,
        "rank_version": raw.get("rank_version"),
    }


def _plain_comparison(notes: str) -> str:
    return (
        notes.replace("metric_relevance", "30-day delay score")
        .replace("postponement_rate", "share waiting past 30 days")
        .replace("unfiltered share", "share of all reviews (loudness)")
        .replace("rank_score", "conversion score")
        .replace("on the 90-day conversion view", "for a buy within 30 days of save (recent 90 days)")
    )
