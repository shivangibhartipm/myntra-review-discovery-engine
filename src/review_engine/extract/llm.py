from __future__ import annotations

from review_engine.config import AppConfig
from review_engine.extract.pipeline import Claim, ground_span
from review_engine.extract.taxonomy import BLOCKERS, JOBS, POSTPONE_VALUES
from review_engine.ollama_client import OllamaError, generate_json

PROMPT = """Extract structured claims from fashion-shopping feedback about why a saved/wishlisted item is not bought within 30 days.

Jobs (pick all that apply): bookmark_later, wait_for_sale, shortlist_compare, intent_blocked, occasion_social, impulse_park
Do not collapse bookmark_later into negative sentiment. intent_blocked is "I want it but a blocker stops me".

Blockers: fit, size_chart, photo_mismatch, fabric_quality, price, sale_timing, review_volume_trust, authenticity, returns, delivery_checkout_saved, styling_occasion, social_validation, competitor_check

postponement_beyond_30d: yes | no | unknown
outside_myntra_info_seeking: true if they check YouTube/haul/Ajio/etc.
segment_clues: only explicit clues (occasion:wedding, platform from text). Never invent demographics.
evidence_span MUST be an exact substring of the text.
sentiment is optional: positive | negative | mixed | null

Return JSON:
{{"jobs":[],"blockers":[],"postponement_beyond_30d":"unknown","outside_myntra_info_seeking":false,"segment_clues":[],"confidence":0.0,"evidence_span":"","sentiment":null}}

Text:
{text}
"""


def llm_extract(doc_id: str, text: str, config: AppConfig) -> Claim | None:
    prompt = PROMPT.format(text=(text or "")[:4000])
    try:
        data = generate_json(host=config.models.ollama_host, model=config.models.generate, prompt=prompt)
    except OllamaError:
        try:
            data = generate_json(
                host=config.models.ollama_host,
                model=config.models.generate_small,
                prompt=prompt,
            )
        except OllamaError:
            return None
    jobs = [j for j in _as_list(data.get("jobs")) if j in JOBS]
    blockers = [b for b in _as_list(data.get("blockers")) if b in BLOCKERS]
    postpone = str(data.get("postponement_beyond_30d") or "unknown")
    if postpone not in POSTPONE_VALUES:
        postpone = "unknown"
    span = ground_span(text, str(data.get("evidence_span") or "") or None)
    return Claim(
        doc_id=doc_id,
        jobs=jobs,
        blockers=blockers,
        postponement_beyond_30d=postpone,
        outside_myntra_info_seeking=bool(data.get("outside_myntra_info_seeking")),
        segment_clues=_as_list(data.get("segment_clues")),
        confidence=float(data.get("confidence") or 0.6),
        evidence_span=span,
        sentiment=_sentiment(data.get("sentiment")),
        source="llm",
    )


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []


def _sentiment(value: object) -> str | None:
    if value in {"positive", "negative", "mixed"}:
        return str(value)
    return None
