"""Keep topic quotes grounded in the opportunity's jobs/blockers."""

from __future__ import annotations

import re
from typing import Any, Mapping

from review_engine.extract.lexical import extract_lexical
from review_engine.wishlist_context import (
    fabric_quality_blocks_saved_purchase,
    fit_blocks_saved_purchase,
    quote_has_saved_item_context,
    returns_blocks_saved_purchase,
    size_chart_blocks_saved_purchase,
)

_OFF_TOPIC = re.compile(
    r"\bdelivery\b|\bcourier\b|\botp\b|\blogin\b|\bsign in\b|\bpassword\b|"
    r"\bcrash\b|force close|keeps stopping|disappointed with myntra.?s delivery",
    re.I,
)

_ORDER_COMPLAINT = re.compile(
    r"\bcancel(?:led|lation|ing)\b|technical issue|shipped.{0,40}cancel|"
    r"very disappointing experience|bad experience with my (very )?first order|"
    r"returned (?:it|the|my|product|item)|after return|return kar|refund|money back|"
    r"return pickup|pickup (?:failed|cancel)|exchange (?:only|option)|replaced the product|"
    r"return process|did not (?:get|receive) (?:my )?refund",
    re.I,
)

_WISHLIST_SAVED = re.compile(
    r"wish\s*list|wishlisted|saved for later|save[d]?\s+for|bookmark|shortlist|\bi saved\b",
    re.I,
)

_PRICE_HESITATION = re.compile(
    r"wish\s*list.{0,100}(expensive|price|overpriced|costly|higher)|"
    r"(expensive|overpriced|too (much|high)).{0,100}wish\s*list|"
    r"price.{0,50}(increase|higher)|salary|when i have money|save[d]?\s+for\s+later",
    re.I,
)

_DISPLAY_PRICE = re.compile(
    r"\bprice\b|expensive|overpriced|costly|higher price|budget|cheaper|salary",
    re.I,
)
_APP_NOISE = re.compile(r"too much data|not opening|crash|keeps stopping|force close", re.I)

DEFAULT_QUOTE_MAX_LEN = 280
MIN_TOPIC_QUOTES = 3
MAX_TOPIC_QUOTES = 6
MIN_DISPLAY_QUOTE_LEN = 25

_BLOCKER_HINTS: dict[str, re.Pattern[str]] = {
    "price": re.compile(r"\bexpensive\b|\bcostly\b|\bprice\b|overpriced|too much|budget|cheaper", re.I),
    "fit": re.compile(r"size chart|won't buy until.{0,30}size|not sure.{0,30}size|not sure.{0,30}fit", re.I),
    "size_chart": re.compile(r"size chart.{0,40}(?:unclear|useless|confus)|won't buy until", re.I),
    "returns": re.compile(
        r"return policy|return.{0,30}(?:risky|risk|worr|scar)|(?:worr|scar|afraid).{0,30}return",
        re.I,
    ),
    "sale_timing": re.compile(r"\beors\b|wait(ing)? for (the )?sale|price drop|on sale", re.I),
    "photo_mismatch": re.compile(r"looks different|photo mismatch|not like the (pic|photo)|haul", re.I),
    "fabric_quality": re.compile(
        r"(?:not sure|uncertain|worri|doubt).{0,30}(?:quality|fabric)|"
        r"(?:quality|fabric).{0,30}(?:worri|uncertain|not sure|before (?:buy|order))",
        re.I,
    ),
    "authenticity": re.compile(r"\bfake\b|authenticit|replica", re.I),
    "competitor_check": re.compile(r"\bajio\b|\bnykaa\b|amazon fashion|\bmeesho\b|\bversus\b|\bvs\b", re.I),
    "review_volume_trust": re.compile(r"not enough reviews|reviews? (are )?not enough", re.I),
    "delivery_checkout_saved": re.compile(r"(wishlist|saved).{0,40}(checkout|payment)", re.I),
}

_JOB_HINTS: dict[str, re.Pattern[str]] = {
    "wait_for_sale": re.compile(r"\beors\b|wait(ing)? for (the )?sale|price drop", re.I),
    "bookmark_later": re.compile(r"save[d]?\s+for\s+later|wish\s*list|salary|baad mein", re.I),
    "shortlist_compare": re.compile(r"confused between|shortlist|\bvs\b|which (one|is better)", re.I),
    "intent_blocked": re.compile(r"won't buy until|size chart|\bfake\b|return policy", re.I),
}


def _topic_keys(mix: Any) -> list[str]:
    if isinstance(mix, dict):
        return [str(k) for k, v in mix.items() if v]
    if isinstance(mix, list):
        return [str(x) for x in mix if x]
    return []


def quote_is_relevant(
    quote: str,
    *,
    jobs: list[str] | None = None,
    blockers: list[str] | None = None,
    full_text: str = "",
) -> bool:
    snippet = (quote or "").strip()
    if not snippet:
        return False

    topic_blockers = [b for b in (blockers or []) if b]
    topic_jobs = [j for j in (jobs or []) if j and j != "unknown"]

    if not quote_has_saved_item_context(snippet):
        return False

    if (
        _OFF_TOPIC.search(snippet)
        and "delivery_checkout_saved" not in topic_blockers
        and not quote_has_saved_item_context(snippet)
    ):
        return False

    if _ORDER_COMPLAINT.search(snippet):
        return False

    if not _snippet_has_topic(snippet, topic_jobs, topic_blockers):
        return False

    if "price" in topic_blockers and "wait_for_sale" not in topic_jobs:
        price_only = not topic_jobs or topic_jobs == ["unknown"]
        if price_only and not (
            _PRICE_HESITATION.search(snippet)
            or (_WISHLIST_SAVED.search(snippet) and _BLOCKER_HINTS["price"].search(snippet))
            or _JOB_HINTS["bookmark_later"].search(snippet)
        ):
            return False

    if "returns" in topic_blockers and not returns_blocks_saved_purchase(snippet):
        if not (full_text and returns_blocks_saved_purchase(full_text)):
            return False

    for blocker, check in (
        ("fit", fit_blocks_saved_purchase),
        ("size_chart", size_chart_blocks_saved_purchase),
        ("fabric_quality", fabric_quality_blocks_saved_purchase),
    ):
        if blocker in topic_blockers and not check(snippet):
            if not (full_text and check(full_text)):
                return False

    return True


def _snippet_has_topic(snippet: str, topic_jobs: list[str], topic_blockers: list[str]) -> bool:
    claim = extract_lexical(snippet)
    quote_blockers = {b for b in claim.blockers if b}
    quote_jobs = {j for j in claim.jobs if j != "unknown"}

    if topic_blockers and quote_blockers.intersection(topic_blockers):
        return True
    if topic_jobs and quote_jobs.intersection(topic_jobs):
        return True

    for blocker in topic_blockers:
        pattern = _BLOCKER_HINTS.get(blocker)
        if pattern and pattern.search(snippet):
            return True

    for job in topic_jobs:
        pattern = _JOB_HINTS.get(job)
        if pattern and pattern.search(snippet):
            return True

    return not topic_blockers and not topic_jobs


def extract_relevant_snippet(
    full_text: str,
    *,
    jobs: list[str] | None = None,
    blockers: list[str] | None = None,
    max_len: int = DEFAULT_QUOTE_MAX_LEN,
) -> str:
    body = (full_text or "").strip()
    if not body:
        return ""

    topic_jobs = [j for j in (jobs or []) if j and j != "unknown"]
    topic_blockers = [b for b in (blockers or []) if b]

    for anchor in (_WISHLIST_SAVED, _PRICE_HESITATION):
        for match in anchor.finditer(body):
            candidate = _extract_window(body, match.start(), max_len=max_len)
            if quote_is_relevant(candidate, jobs=topic_jobs, blockers=topic_blockers, full_text=body):
                return candidate

    patterns: list[re.Pattern[str]] = []
    for blocker in topic_blockers:
        pattern = _BLOCKER_HINTS.get(blocker)
        if pattern:
            patterns.append(pattern)
    for job in topic_jobs:
        pattern = _JOB_HINTS.get(job)
        if pattern:
            patterns.append(pattern)

    best = ""
    for pattern in patterns:
        for match in pattern.finditer(body):
            candidate = _extract_window(body, match.start(), max_len=max_len)
            if _OFF_TOPIC.search(candidate[:40]):
                candidate = _extract_window(body, match.start(), max_len=max_len)
            if len(candidate) > len(best) and quote_has_saved_item_context(candidate) and quote_is_relevant(
                candidate,
                jobs=topic_jobs,
                blockers=topic_blockers,
                full_text=body,
            ):
                best = candidate
    return best


def filter_quotes_for_opportunity(
    quotes: list[dict[str, str]],
    *,
    jobs: list[str] | None = None,
    blockers: list[str] | None = None,
    job_mix: dict[str, float] | None = None,
    blocker_mix: dict[str, float] | None = None,
    documents: Mapping[str, Mapping[str, Any]] | None = None,
    enrichments: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, str]]:
    topic_jobs = jobs or _topic_keys(job_mix)
    topic_blockers = blockers or _topic_keys(blocker_mix)
    kept: list[dict[str, str]] = []

    for raw in quotes:
        if not isinstance(raw, dict):
            continue
        doc_id = str(raw.get("doc_id") or "")
        quote = str(raw.get("quote") or "")
        doc = (documents or {}).get(doc_id) or {}
        enr = (enrichments or {}).get(doc_id) or {}
        full_text = str(doc.get("text") or "")
        span = str(enr.get("evidence_span") or "")
        member_jobs = _topic_keys(enr.get("jobs")) or topic_jobs
        member_blockers = _topic_keys(enr.get("blockers")) or topic_blockers

        candidates = [quote]
        if span and span not in candidates:
            candidates.insert(0, span)
        mined = extract_relevant_snippet(
            full_text,
            jobs=member_jobs,
            blockers=member_blockers,
        )
        if mined and mined not in candidates:
            candidates.insert(0, mined)

        for candidate in candidates:
            if not candidate:
                continue
            if quote_is_relevant(
                candidate,
                jobs=member_jobs,
                blockers=member_blockers,
                full_text=full_text or candidate,
            ):
                polished = polish_quote(candidate, full_text)
                if _is_displayable_quote(polished) and quote_has_saved_item_context(polished):
                    kept.append({**raw, "quote": polished})
                    break

    return kept


def _word_boundary_start(body: str, pos: int) -> int:
    pos = max(0, min(pos, len(body)))
    window = body[max(0, pos - 120) : pos]
    for sep in (". ", "? ", "! ", "....", "...", "\n"):
        idx = window.rfind(sep)
        if idx >= 0:
            return max(0, pos - len(window) + idx + len(sep))
    while pos > 0 and body[pos - 1] not in " \n\t":
        pos -= 1
    return pos


def _word_boundary_end(body: str, start: int, max_len: int) -> int:
    end = min(len(body), start + max_len)
    while end < len(body) and end > start and body[end - 1] not in " \n\t.!?":
        end += 1
    chunk = body[start:end]
    for sep in (". ", "? ", "! "):
        idx = chunk.rfind(sep)
        if idx >= 40:
            return start + idx + 1
    return end


def _extract_window(body: str, anchor_start: int, *, max_len: int = DEFAULT_QUOTE_MAX_LEN) -> str:
    if not body:
        return ""
    start = _word_boundary_start(body, anchor_start)
    end = _word_boundary_end(body, start, max_len)
    snippet = body[start:end].strip()
    return snippet.lstrip(".,;:- ").strip()


def _is_displayable_quote(quote: str) -> bool:
    text = (quote or "").strip()
    return len(text) >= MIN_DISPLAY_QUOTE_LEN and len(text.split()) >= 4


def polish_quote(quote: str, full_text: str = "", *, max_len: int = DEFAULT_QUOTE_MAX_LEN) -> str:
    snippet = (quote or "").strip()
    body = (full_text or "").strip()
    if not snippet:
        return ""
    result = snippet
    if body and snippet in body:
        idx = body.find(snippet)
        result = _extract_window(body, idx, max_len=max(max_len, len(snippet) + 40))
    elif body:
        for probe_len in (min(len(snippet), 80), min(len(snippet), 48), min(len(snippet), 32)):
            probe = snippet[-probe_len:]
            if len(probe) < 12:
                continue
            idx = body.find(probe)
            if idx >= 0:
                result = _extract_window(body, idx, max_len=max_len)
                break
    if body and not quote_has_saved_item_context(result):
        for anchor in (_WISHLIST_SAVED, _PRICE_HESITATION):
            match = anchor.search(body)
            if match:
                expanded = _extract_window(body, match.start(), max_len=max_len)
                if quote_has_saved_item_context(expanded):
                    return expanded
    return result


def fill_topic_quotes(
    quotes: list[dict[str, str]],
    *,
    member_doc_ids: list[str],
    jobs: list[str] | None = None,
    blockers: list[str] | None = None,
    job_mix: dict[str, float] | None = None,
    blocker_mix: dict[str, float] | None = None,
    documents: Mapping[str, Mapping[str, Any]] | None = None,
    enrichments: Mapping[str, Mapping[str, Any]] | None = None,
    min_quotes: int = MIN_TOPIC_QUOTES,
    max_quotes: int = MAX_TOPIC_QUOTES,
) -> list[dict[str, str]]:
    if len(quotes) >= min_quotes:
        return quotes[:max_quotes]

    topic_jobs = jobs or _topic_keys(job_mix)
    topic_blockers = blockers or _topic_keys(blocker_mix)
    seen = {str(q.get("doc_id") or "") for q in quotes}
    filled = list(quotes)

    for doc_id in member_doc_ids:
        if len(filled) >= max_quotes:
            break
        if doc_id in seen:
            continue
        doc = (documents or {}).get(str(doc_id)) or {}
        enr = (enrichments or {}).get(str(doc_id)) or {}
        source = str(doc.get("source") or "")
        if not source:
            continue
        full_text = str(doc.get("text") or "")
        if not full_text:
            continue
        member_jobs = _topic_keys(enr.get("jobs")) or topic_jobs
        member_blockers = _topic_keys(enr.get("blockers")) or topic_blockers

        candidate = extract_relevant_snippet(
            full_text,
            jobs=member_jobs,
            blockers=member_blockers,
        )
        span = str(enr.get("evidence_span") or "")
        if not candidate and span:
            candidate = polish_quote(span, full_text)
        if not candidate:
            candidate = _relaxed_topic_snippet(
                full_text,
                topic_jobs=member_jobs,
                topic_blockers=member_blockers,
            )
        if not candidate:
            candidate = _display_fallback_snippet(full_text, topic_blockers)

        if not candidate:
            continue

        polished = polish_quote(candidate, full_text)
        if not _is_displayable_quote(polished) or not quote_has_saved_item_context(polished):
            continue
        if not quote_is_relevant(
            polished,
            jobs=member_jobs,
            blockers=member_blockers,
            full_text=full_text,
        ):
            continue

        filled.append(
            {
                "doc_id": str(doc_id),
                "source": source,
                "observed_at": str(doc.get("observed_at") or ""),
                "quote": polished,
            }
        )
        seen.add(str(doc_id))

    return filled[:max_quotes]


def _relaxed_topic_snippet(
    full_text: str,
    *,
    topic_jobs: list[str],
    topic_blockers: list[str],
    max_len: int = DEFAULT_QUOTE_MAX_LEN,
) -> str:
    body = (full_text or "").strip()
    if not body:
        return ""

    if "price" in topic_blockers and (
        _WISHLIST_SAVED.search(body) or _JOB_HINTS["bookmark_later"].search(body)
    ):
        for pattern in (_PRICE_HESITATION, _BLOCKER_HINTS["price"]):
            match = pattern.search(body)
            if match:
                snippet = _extract_window(body, match.start(), max_len=max_len)
                if (
                    quote_has_saved_item_context(snippet)
                    and not _OFF_TOPIC.search(snippet[:40])
                    and not _ORDER_COMPLAINT.search(snippet)
                ):
                    return snippet

    for blocker in topic_blockers:
        pattern = _BLOCKER_HINTS.get(blocker)
        if not pattern:
            continue
        match = pattern.search(body)
        if match:
            snippet = _extract_window(body, match.start(), max_len=max_len)
            if (
                quote_has_saved_item_context(snippet)
                and not _OFF_TOPIC.search(snippet[:40])
                and not _ORDER_COMPLAINT.search(snippet)
            ):
                return snippet

    for job in topic_jobs:
        pattern = _JOB_HINTS.get(job)
        if not pattern:
            continue
        match = pattern.search(body)
        if match:
            snippet = _extract_window(body, match.start(), max_len=max_len)
            if (
                quote_has_saved_item_context(snippet)
                and not _OFF_TOPIC.search(snippet[:40])
                and not _ORDER_COMPLAINT.search(snippet)
            ):
                return snippet

    return ""


def _display_fallback_snippet(
    full_text: str,
    topic_blockers: list[str],
    *,
    max_len: int = DEFAULT_QUOTE_MAX_LEN,
) -> str:
    body = (full_text or "").strip()
    if not body:
        return ""
    if _OFF_TOPIC.search(body[:80]) and "delivery_checkout_saved" not in topic_blockers:
        return ""

    for blocker in topic_blockers:
        pattern = _BLOCKER_HINTS.get(blocker)
        if not pattern:
            continue
        match = pattern.search(body)
        if not match:
            continue
        snippet = _extract_window(body, match.start(), max_len=max_len)
        if (
            not snippet
            or not quote_has_saved_item_context(snippet)
            or _ORDER_COMPLAINT.search(snippet)
            or _APP_NOISE.search(snippet)
        ):
            continue
        if blocker == "price" and not _DISPLAY_PRICE.search(snippet):
            continue
        return snippet

    for job, pattern in _JOB_HINTS.items():
        match = pattern.search(body)
        if not match:
            continue
        snippet = _extract_window(body, match.start(), max_len=max_len)
        if (
            snippet
            and quote_has_saved_item_context(snippet)
            and not _ORDER_COMPLAINT.search(snippet)
            and not _OFF_TOPIC.search(snippet[:40])
        ):
            return snippet

    return ""
