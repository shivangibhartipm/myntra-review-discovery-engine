from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from review_engine.config import AppConfig
from review_engine.ollama_client import OllamaError, generate_json
from review_engine.relevance.lexical import KNOWN_TAGS, LexicalResult

JudgeFn = Callable[[str, LexicalResult], "JudgeResult"]

PROMPT = """You are filtering public fashion-shopping feedback for a Growth team.
Decide if the text is relevant to why someone delays buying a saved / wishlisted / shortlisted item within 30 days of adding it.

Relevant (true): wishlist/save/shortlist; waiting for a sale or salary; comparing options; size/fit uncertainty; styling or occasion hold; review-seeking; trust/quality doubt before buying; stock unavailable on a saved item; wishlist graveyard / never-buy behavior; wishlist UX friction; conversion stories (finally bought from wishlist); returns/fake fear that blocks buying a saved item; checkout/payment failing on a saved item.
Not relevant (false): OTP/login only; generic app crash; late delivery with no save/wishlist; post-purchase return/refund complaints with no saved-item hesitation; post-purchase wrong-size or quality praise with no save/hesitation; spam; one-word comments; brand hate with no purchase-delay content.

Keep-if-borderline: waiting for sale or comparing two products still counts even without the word "wishlist".

Return JSON only:
{{"is_relevant": true, "score": 0.0, "tags": ["wishlist_language"], "rationale": "short"}}
Allowed tags: {tags}

Text:
{text}
"""


@dataclass(frozen=True)
class JudgeResult:
    is_relevant: bool
    score: float
    tags: tuple[str, ...]
    source: str  # llm | heuristic
    error: str | None = None


def llm_judge(text: str, lexical: LexicalResult, config: AppConfig) -> JudgeResult:
    prompt = PROMPT.format(tags=", ".join(KNOWN_TAGS), text=text[:4000])
    model = config.models.generate
    try:
        data = generate_json(host=config.models.ollama_host, model=model, prompt=prompt)
    except OllamaError:
        try:
            data = generate_json(
                host=config.models.ollama_host,
                model=config.models.generate_small,
                prompt=prompt,
            )
        except OllamaError as exc:
            return JudgeResult(False, 0.0, lexical.tags, "llm_error", str(exc))
    tags = _clean_tags(data.get("tags") or lexical.tags)
    score = _clip_score(data.get("score"))
    relevant = bool(data.get("is_relevant"))
    return JudgeResult(relevant, score, tags or lexical.tags, "llm")


def heuristic_judge(text: str, lexical: LexicalResult, config: AppConfig) -> JudgeResult:
    del text, config
    from review_engine.relevance.lexical import heuristic_score

    score = heuristic_score(lexical.tags, lexical.gated)
    relevant = score >= 0.5
    return JudgeResult(relevant, score, lexical.tags, "heuristic")


def _clean_tags(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return ()
    allowed = set(KNOWN_TAGS)
    out = []
    for item in raw:
        tag = str(item).strip()
        if tag in allowed and tag not in out:
            out.append(tag)
    return tuple(out)


def _clip_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))
