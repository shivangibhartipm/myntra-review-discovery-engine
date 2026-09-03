from __future__ import annotations

from dataclasses import dataclass

from review_engine.config import AppConfig, FilterConfig
from review_engine.relevance.judge import JudgeFn, JudgeResult, heuristic_judge, llm_judge
from review_engine.relevance.lexical import BORDERLINE_KEEP_TAGS, lexical_gate

FILTER_VERSION = "filter_v1"


@dataclass(frozen=True)
class FilterDecision:
    is_relevant: bool
    relevance_score: float
    relevance_reasons: tuple[str, ...]
    filter_version: str
    gated: bool
    judge_source: str


def classify_text(
    text: str,
    config: AppConfig,
    judge: JudgeFn | None = None,
) -> FilterDecision:
    filt: FilterConfig = config.filter
    lexical = lexical_gate(text)
    if not lexical.gated:
        return FilterDecision(
            is_relevant=False,
            relevance_score=0.0,
            relevance_reasons=(lexical.gate_reason,) if lexical.gate_reason else (),
            filter_version=filt.version,
            gated=False,
            judge_source="lexical_reject",
        )

    if judge is not None:
        judged = judge(text, lexical)
    elif filt.use_llm:
        judged = llm_judge(text, lexical, config)
        if judged.source == "llm_error":
            judged = heuristic_judge(text, lexical, config)
    else:
        judged = heuristic_judge(text, lexical, config)

    return _apply_thresholds(lexical.tags, judged, filt)


def _apply_thresholds(lex_tags: tuple[str, ...], judged: JudgeResult, filt: FilterConfig) -> FilterDecision:
    tags = judged.tags or lex_tags
    score = judged.score
    relevant = judged.is_relevant or score >= filt.relevance_threshold
    if tags and (BORDERLINE_KEEP_TAGS & set(tags)) and score >= filt.borderline_threshold:
        relevant = True
        score = max(score, filt.relevance_threshold)
    if not relevant and score >= filt.relevance_threshold:
        relevant = True
    return FilterDecision(
        is_relevant=relevant,
        relevance_score=round(score, 4),
        relevance_reasons=tags or (("gated_broad",) if judged.source else ()),
        filter_version=filt.version,
        gated=True,
        judge_source=judged.source,
    )
