"""Composite rank_score for Phase 5.

Default product view is the 90-day slice. Weights live in config.yaml under `rank`.

rank_score =
    w1 * (metric_relevance / 5)
  + w2 * postponement_rate
  + w3 * prevalence_relevant
  + w4 * recency_90d_share
  + w5 * actionability
  − w6 * loud_but_weak_penalty

metric_relevance is stored on 1–5 and scaled to 0–1 so weights are comparable.
loud_but_weak_penalty is high when unfiltered share is high and metric_relevance is low
(so 1-star Play delivery volume cannot dominate wishlist conversion rank).
"""

from __future__ import annotations

from review_engine.config import RankConfig
from review_engine.rank.rubrics import loud_but_weak_penalty


def recency_boost(recency_90d_share: float) -> float:
    return max(0.0, min(1.0, recency_90d_share))


def rank_score(
    *,
    metric_rel: float,
    postponement_rate: float,
    prevalence_relevant: float,
    recency_90d_share: float,
    actionability_score: float,
    prevalence_unfiltered: float,
    weights: RankConfig,
) -> float:
    penalty = loud_but_weak_penalty(prevalence_unfiltered, metric_rel)
    raw = (
        weights.w1_metric_relevance * (metric_rel / 5.0)
        + weights.w2_postponement_rate * postponement_rate
        + weights.w3_prevalence_relevant * prevalence_relevant
        + weights.w4_recency_boost * recency_boost(recency_90d_share)
        + weights.w5_actionability * actionability_score
        - weights.w6_loud_but_weak_penalty * penalty
    )
    return round(raw, 6)
