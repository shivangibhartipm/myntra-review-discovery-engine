from __future__ import annotations

from dataclasses import asdict, dataclass

from review_engine.config import AppConfig
from review_engine.extract.lexical import LexicalClaim, extract_lexical
from review_engine.extract.taxonomy import BLOCKERS, JOBS, POSTPONE_VALUES

EXTRACT_VERSION = "extract_v1"


@dataclass
class Claim:
    doc_id: str
    jobs: list[str]
    blockers: list[str]
    postponement_beyond_30d: str
    outside_myntra_info_seeking: bool
    segment_clues: list[str]
    confidence: float
    evidence_span: str
    sentiment: str | None = None
    source: str = "lexical"

    def as_dict(self) -> dict:
        return asdict(self)


def ground_span(text: str, span: str | None) -> str:
    body = text or ""
    if not span:
        return ""
    if span in body:
        return span
    idx = body.lower().find(span.lower())
    if idx >= 0:
        return body[idx : idx + len(span)]
    return ""


def merge_claims(
    doc_id: str,
    text: str,
    lexical: LexicalClaim,
    llm: Claim | None,
) -> Claim:
    """Union obvious lexical hits (eors, wishlist) with LLM; require a grounded span."""
    jobs = list(lexical.jobs)
    blockers = list(lexical.blockers)
    postpone = lexical.postponement_beyond_30d
    outside = lexical.outside_myntra_info_seeking
    clues = list(lexical.segment_clues)
    span = lexical.evidence_span
    confidence = lexical.confidence
    sentiment = None
    source = "lexical"
    if llm is not None:
        source = "lexical+llm" if jobs or blockers else "llm"
        jobs = _uniq([j for j in llm.jobs + jobs if j in JOBS])
        blockers = _uniq([b for b in llm.blockers + blockers if b in BLOCKERS])
        if llm.postponement_beyond_30d in POSTPONE_VALUES:
            postpone = llm.postponement_beyond_30d
        outside = bool(llm.outside_myntra_info_seeking or outside)
        clues = _uniq(llm.segment_clues + clues)
        grounded = ground_span(text, llm.evidence_span)
        if grounded:
            span = grounded
        confidence = max(confidence, llm.confidence)
        sentiment = llm.sentiment
        source = "llm" if llm.source == "llm" else source
    jobs = [j for j in jobs if j != "unknown"]
    if not jobs and not blockers:
        jobs = ["unknown"]
    span = ground_span(text, span) or (text[:80] if text else "")
    if span and span not in text:
        span = ground_span(text, span)
    return Claim(
        doc_id=doc_id,
        jobs=jobs or ["unknown"],
        blockers=blockers,
        postponement_beyond_30d=postpone if postpone in POSTPONE_VALUES else "unknown",
        outside_myntra_info_seeking=outside,
        segment_clues=clues,
        confidence=round(min(max(confidence, 0.0), 1.0), 4),
        evidence_span=span,
        sentiment=sentiment,
        source=source,
    )


def extract_claim(
    *,
    doc_id: str,
    text: str,
    config: AppConfig,
    source: str = "",
    category: str = "",
    llm_fn=None,
) -> Claim:
    lexical = extract_lexical(text, source=source, category=category)
    llm_claim = None
    use_llm = config.extract.use_llm
    if llm_fn is not None:
        llm_claim = llm_fn(doc_id, text, lexical)
    elif use_llm:
        from review_engine.extract.llm import llm_extract

        llm_claim = llm_extract(doc_id, text, config)
    return merge_claims(doc_id, text, lexical, llm_claim)


def _uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out
