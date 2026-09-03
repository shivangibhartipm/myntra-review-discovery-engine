from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Iterable

from review_engine.cluster.embed import parse_json_list
from review_engine.config import RankConfig
from review_engine.rank.rubrics import actionability, delay_mechanism, metric_relevance
from review_engine.rank.scoring import rank_score
from review_engine.windows import Cutoffs

APP_STORE_SOURCES = {"play", "app_store"}
HIGH_SIGNAL_SOURCES = {"reddit", "youtube"}
INTENT_JOBS = {"intent_blocked"}
BOOKMARK_JOBS = {"bookmark_later", "impulse_park"}


@dataclass
class MemberSnap:
    doc_id: str
    source: str
    observed_at: datetime | None
    layer: str | None
    jobs: list[str]
    blockers: list[str]
    postpone: str
    segment_clues: list[str]


@dataclass
class RankedOpportunity:
    opportunity_id: str
    problem_one_liner: str
    member_n: int
    prevalence_relevant: float
    prevalence_unfiltered: float
    recency_90d_share: float
    postponement_rate: float
    intent_vs_bookmark: dict[str, float]
    multi_source_support: float
    metric_relevance: float
    actionability: float
    rank_score: float
    rank_score_90d: float
    rank_score_12m: float
    delay_mechanism: str
    job_mix: dict[str, float]
    blocker_mix: dict[str, float]
    source_mix: dict[str, float]
    rank_version: str
    quotes: list[dict[str, str]] = field(default_factory=list)
    segment_slices: list[dict[str, Any]] = field(default_factory=list)
    comparison_notes: str = ""
    rank_90d: int | None = None
    rank_12m: int | None = None
    volume_rank: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_observed_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", ""))
    except ValueError:
        return None


def member_from_row(row: Any) -> MemberSnap:
    jobs = parse_json_list(row["jobs"] if not isinstance(row, dict) else row.get("jobs"))
    blockers = parse_json_list(row["blockers"] if not isinstance(row, dict) else row.get("blockers"))
    clues = parse_json_list(
        row["segment_clues"] if not isinstance(row, dict) else row.get("segment_clues")
    )
    postpone = row["postponement_beyond_30d"] if not isinstance(row, dict) else row.get("postponement_beyond_30d")
    return MemberSnap(
        doc_id=row["doc_id"],
        source=row["source"] or "",
        observed_at=parse_observed_at(row["observed_at"] if not isinstance(row, dict) else row.get("observed_at")),
        layer=row["corpus_layer"] if not isinstance(row, dict) else row.get("corpus_layer"),
        jobs=jobs,
        blockers=blockers,
        postpone=str(postpone or "unknown"),
        segment_clues=clues,
    )


def _in_window(member: MemberSnap, start: datetime | None) -> bool:
    if start is None or member.observed_at is None:
        return True
    return member.observed_at >= start


def _share(numer: int, denom: int) -> float:
    if denom <= 0:
        return 0.0
    return round(numer / denom, 4)


def _job_blocker_mix(members: list[MemberSnap]) -> tuple[dict[str, float], dict[str, float]]:
    jobs: dict[str, int] = {}
    blockers: dict[str, int] = {}
    for member in members:
        for job in member.jobs:
            jobs[job] = jobs.get(job, 0) + 1
        for blocker in member.blockers:
            blockers[blocker] = blockers.get(blocker, 0) + 1
    n = len(members) or 1
    job_mix = {k: round(v / n, 4) for k, v in sorted(jobs.items(), key=lambda kv: (-kv[1], kv[0]))}
    blocker_mix = {k: round(v / n, 4) for k, v in sorted(blockers.items(), key=lambda kv: (-kv[1], kv[0]))}
    return job_mix, blocker_mix


def _source_mix(members: list[MemberSnap]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for member in members:
        src = member.source or "unknown"
        counts[src] = counts.get(src, 0) + 1
    n = len(members) or 1
    return {k: round(v / n, 4) for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))}


def intent_vs_bookmark(members: list[MemberSnap]) -> dict[str, float]:
    intent = sum(1 for m in members if any(j in INTENT_JOBS for j in m.jobs))
    bookmark = sum(
        1
        for m in members
        if any(j in BOOKMARK_JOBS for j in m.jobs) and not any(j in INTENT_JOBS for j in m.jobs)
    )
    other = max(0, len(members) - intent - bookmark)
    n = len(members) or 1
    return {
        "intent_blocked": round(intent / n, 4),
        "bookmark_or_impulse": round(bookmark / n, 4),
        "other": round(other / n, 4),
    }


def multi_source_support(source_mix: dict[str, float]) -> float:
    sources = {s for s, share in source_mix.items() if share > 0}
    if not sources:
        return 0.0
    if sources & HIGH_SIGNAL_SOURCES:
        return 1.0
    if len(sources) >= 2:
        return 0.7
    if sources <= APP_STORE_SOURCES:
        return 0.35
    return 0.5


def segment_slices(members: list[MemberSnap], min_n: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[MemberSnap]] = {}
    for member in members:
        for clue in member.segment_clues:
            if clue:
                buckets.setdefault(clue, []).append(member)
    out = []
    for clue, group in sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(group) < min_n:
            continue
        out.append(
            {
                "clue": clue,
                "n": len(group),
                "postponement_rate": _share(sum(1 for m in group if m.postpone == "yes"), len(group)),
            }
        )
    return out


def metrics_for_slice(
    members: list[MemberSnap],
    *,
    n_relevant_slice: int,
    n_unfiltered: int,
    job_mix: dict[str, float],
    blocker_mix: dict[str, float],
    source_mix: dict[str, float],
    recency_share: float,
    weights: RankConfig,
) -> dict[str, float]:
    postponement_rate = _share(sum(1 for m in members if m.postpone == "yes"), len(members))
    prevalence_relevant = _share(len(members), n_relevant_slice)
    prevalence_unfiltered = _share(len(members), n_unfiltered)
    metric_rel = metric_relevance(job_mix, blocker_mix)
    act = actionability(job_mix, blocker_mix)
    score = rank_score(
        metric_rel=metric_rel,
        postponement_rate=postponement_rate,
        prevalence_relevant=prevalence_relevant,
        recency_90d_share=recency_share,
        actionability_score=act,
        prevalence_unfiltered=prevalence_unfiltered,
        weights=weights,
    )
    return {
        "postponement_rate": postponement_rate,
        "prevalence_relevant": prevalence_relevant,
        "prevalence_unfiltered": prevalence_unfiltered,
        "metric_relevance": metric_rel,
        "actionability": act,
        "rank_score": score,
        "multi_source_support": multi_source_support(source_mix),
    }


def rank_opportunities(
    opportunities: Iterable[dict[str, Any]],
    members_by_id: dict[str, MemberSnap],
    *,
    n_relevant: int,
    n_unfiltered: int,
    bounds: Cutoffs,
    weights: RankConfig,
) -> list[RankedOpportunity]:
    n_relevant_90d = sum(1 for m in members_by_id.values() if _in_window(m, bounds.recency_start))
    ranked: list[RankedOpportunity] = []
    for opp in opportunities:
        member_ids = _as_id_list(opp.get("member_doc_ids") or opp.get("member_ids"))
        members = [members_by_id[i] for i in member_ids if i in members_by_id]
        if not members:
            continue
        job_mix = _as_mix(opp.get("job_mix"))
        blocker_mix = _as_mix(opp.get("blocker_mix"))
        source_mix = _as_mix(opp.get("source_mix"))
        inferred_jobs, inferred_blockers = _job_blocker_mix(members)
        job_mix = job_mix or inferred_jobs
        blocker_mix = blocker_mix or inferred_blockers
        source_mix = source_mix or _source_mix(members)

        members_90d = [m for m in members if _in_window(m, bounds.recency_start)]
        recency_share = _share(len(members_90d), len(members))
        full = metrics_for_slice(
            members,
            n_relevant_slice=n_relevant,
            n_unfiltered=n_unfiltered,
            job_mix=job_mix,
            blocker_mix=blocker_mix,
            source_mix=source_mix,
            recency_share=recency_share,
            weights=weights,
        )
        slice_90 = metrics_for_slice(
            members_90d or members,
            n_relevant_slice=n_relevant_90d or n_relevant,
            n_unfiltered=n_unfiltered,
            job_mix=job_mix,
            blocker_mix=blocker_mix,
            source_mix=source_mix,
            recency_share=1.0 if members_90d else recency_share,
            weights=weights,
        )
        quotes = _as_quotes(opp.get("quotes"))
        ranked.append(
            RankedOpportunity(
                opportunity_id=str(opp["opportunity_id"]),
                problem_one_liner=str(opp.get("problem_one_liner") or ""),
                member_n=len(members),
                prevalence_relevant=full["prevalence_relevant"],
                prevalence_unfiltered=full["prevalence_unfiltered"],
                recency_90d_share=recency_share,
                postponement_rate=full["postponement_rate"],
                intent_vs_bookmark=intent_vs_bookmark(members),
                multi_source_support=full["multi_source_support"],
                metric_relevance=full["metric_relevance"],
                actionability=full["actionability"],
                rank_score=slice_90["rank_score"],
                rank_score_90d=slice_90["rank_score"],
                rank_score_12m=full["rank_score"],
                delay_mechanism=delay_mechanism(job_mix, blocker_mix),
                job_mix=job_mix,
                blocker_mix=blocker_mix,
                source_mix=source_mix,
                rank_version=weights.version,
                quotes=quotes,
                segment_slices=segment_slices(members, weights.min_segment_n),
            )
        )

    by_90d = sorted(ranked, key=lambda o: (-o.rank_score_90d, -o.metric_relevance, o.opportunity_id))
    by_12m = sorted(ranked, key=lambda o: (-o.rank_score_12m, -o.metric_relevance, o.opportunity_id))
    by_volume = sorted(ranked, key=lambda o: (-o.prevalence_unfiltered, -o.member_n, o.opportunity_id))
    for i, opp in enumerate(by_90d, start=1):
        opp.rank_90d = i
    for i, opp in enumerate(by_12m, start=1):
        opp.rank_12m = i
    for i, opp in enumerate(by_volume, start=1):
        opp.volume_rank = i
    _attach_comparisons(by_90d, weights.top_n_compare)
    return by_90d


def volume_order_differs(ranked: list[RankedOpportunity]) -> bool:
    if len(ranked) < 2:
        return False
    metric_ids = [o.opportunity_id for o in ranked]
    volume_ids = [o.opportunity_id for o in sorted(ranked, key=lambda x: (x.volume_rank or 0))]
    return metric_ids != volume_ids


def _attach_comparisons(ordered: list[RankedOpportunity], top_n: int) -> None:
    horizon = ordered[: max(0, top_n)] or ordered
    for i, opp in enumerate(horizon):
        nxt = horizon[i + 1] if i + 1 < len(horizon) else (ordered[i + 1] if i + 1 < len(ordered) else None)
        if nxt is None:
            opp.comparison_notes = (
                f"{opp.opportunity_id} is last among scored themes; metric_relevance={opp.metric_relevance:.0f}."
            )
            continue
        reasons = []
        if opp.metric_relevance != nxt.metric_relevance:
            direction = "higher" if opp.metric_relevance > nxt.metric_relevance else "lower"
            reasons.append(
                f"{direction} metric_relevance ({opp.metric_relevance:.0f} vs {nxt.metric_relevance:.0f})"
            )
        if opp.postponement_rate != nxt.postponement_rate:
            direction = "higher" if opp.postponement_rate > nxt.postponement_rate else "lower"
            reasons.append(
                f"{direction} postponement_rate ({opp.postponement_rate:.2f} vs {nxt.postponement_rate:.2f})"
            )
        if nxt.prevalence_unfiltered > opp.prevalence_unfiltered:
            reasons.append(
                f"beats {nxt.opportunity_id} despite lower unfiltered share "
                f"({opp.prevalence_unfiltered:.3f} vs {nxt.prevalence_unfiltered:.3f})"
            )
        why = "; ".join(reasons) or "composite rank_score is higher on the 90-day view"
        opp.comparison_notes = (
            f"{opp.opportunity_id} outranks {nxt.opportunity_id} on the 90-day conversion view: {why}."
        )


def _as_id_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return [raw] if raw else []
        if isinstance(value, list):
            return [str(x) for x in value]
    return []


def _as_mix(raw: Any) -> dict[str, float]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {str(k): float(v) for k, v in raw.items()}
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(value, dict):
            return {str(k): float(v) for k, v in value.items()}
    return {}


def _as_quotes(raw: Any) -> list[dict[str, str]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []
