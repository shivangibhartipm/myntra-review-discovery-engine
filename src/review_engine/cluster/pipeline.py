from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from review_engine.cluster.embed import (
    claim_embed_text,
    concat_vectors,
    dense_embed,
    histogram,
    parse_json_list,
    parse_stored_embedding,
    tag_vector,
)
from review_engine.cluster.group import (
    Cluster,
    Member,
    agglomerative_cluster,
    expand_if_too_few,
    merge_duplicates,
    reassign_tiny,
    split_mixed_clusters,
    target_k,
)
from review_engine.cluster.naming import (
    llm_one_liner,
    load_overrides,
    opportunity_id,
    template_one_liner,
    top_key,
)
from review_engine.config import AppConfig
from review_engine.present.quote_relevance import extract_relevant_snippet, quote_is_relevant


@dataclass
class NamedOpportunity:
    opportunity_id: str
    problem_one_liner: str
    member_doc_ids: list[str]
    representative_doc_ids: list[str]
    job_mix: dict[str, float]
    blocker_mix: dict[str, float]
    source_mix: dict[str, float]
    single_source_warning: bool
    quotes: list[dict[str, str]]
    naming_source: str
    cluster_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "problem_one_liner": self.problem_one_liner,
            "member_doc_ids": self.member_doc_ids,
            "representative_doc_ids": self.representative_doc_ids,
            "job_mix": self.job_mix,
            "blocker_mix": self.blocker_mix,
            "source_mix": self.source_mix,
            "single_source_warning": self.single_source_warning,
            "quotes": self.quotes,
            "naming_source": self.naming_source,
            "cluster_version": self.cluster_version,
        }


def _field(row: Any, name: str, default=""):
    if isinstance(row, dict):
        return row.get(name, default)
    try:
        value = row[name]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def build_member(row: Any, vector: list[float]) -> Member:
    jobs = parse_json_list(_field(row, "jobs", []))
    blockers = parse_json_list(_field(row, "blockers", []))
    return Member(
        doc_id=_field(row, "doc_id"),
        source=_field(row, "source") or "",
        observed_at=_field(row, "observed_at") or None,
        text=_field(row, "text") or "",
        jobs=jobs,
        blockers=blockers,
        evidence_span=_field(row, "evidence_span") or "",
        postponement=_field(row, "postponement_beyond_30d", "unknown") or "unknown",
        vector=vector,
    )


def vector_for_row(row: Any, *, config: AppConfig, use_dense: bool) -> list[float]:
    jobs = parse_json_list(_field(row, "jobs", []))
    blockers = parse_json_list(_field(row, "blockers", []))
    text = _field(row, "text", "") or ""
    span = _field(row, "evidence_span", "") or ""
    postpone = _field(row, "postponement_beyond_30d", "unknown") or "unknown"
    tags = tag_vector(jobs=jobs, blockers=blockers, postponement=postpone, text=text)
    dense = None
    if use_dense:
        stored = parse_stored_embedding(_field(row, "embedding", None))
        prompt = claim_embed_text(text=text, jobs=jobs, blockers=blockers, evidence_span=span)
        dense = stored if stored and len(stored) > 40 else dense_embed(
            prompt,
            host=config.models.ollama_host,
            model=config.models.embed,
        )
    return concat_vectors(tags, dense)


def cluster_members(
    members: list[Member],
    *,
    min_k: int,
    max_k: int,
    min_size: int,
    merge_cosine: float,
) -> list[Cluster]:
    if not members:
        return []
    k = target_k(len(members), min_k, max_k)
    clusters = agglomerative_cluster(members, k)
    clusters = split_mixed_clusters(clusters)
    clusters = merge_duplicates(clusters, merge_cosine, max_k)
    clusters = reassign_tiny(clusters, min_size if len(members) >= min_size else 1)
    clusters = expand_if_too_few(clusters, members, min_k, max_k)
    clusters = split_mixed_clusters(clusters)
    clusters = merge_duplicates(clusters, merge_cosine, max_k)
    return [c for c in clusters if c.members]


def name_clusters(
    clusters: list[Cluster],
    *,
    config: AppConfig,
    use_llm: bool,
    llm_fn: Callable[[Cluster, list[str]], str | None] | None = None,
) -> list[NamedOpportunity]:
    overrides = load_overrides(config.cluster.name_overrides_path)
    used_ids: set[str] = set()
    out: list[NamedOpportunity] = []
    for cluster in clusters:
        job_mix = histogram(cluster.job_values())
        blocker_mix = histogram(cluster.blocker_values())
        source_mix = histogram(cluster.sources())
        reps, quotes = pick_representatives(cluster, job_mix=job_mix, blocker_mix=blocker_mix)
        template = template_one_liner(cluster)
        naming = "template"
        line = template
        quote_texts = [q["quote"] for q in quotes if q.get("quote")]
        if llm_fn is not None:
            llm_line = llm_fn(cluster, quote_texts)
        elif use_llm:
            llm_line = llm_one_liner(cluster, config, quote_texts)
        else:
            llm_line = None
        if llm_line and not _banned(llm_line):
            line = llm_line
            naming = "llm"
        oid = opportunity_id(top_key(job_mix), top_key(blocker_mix), used_ids)
        if oid in overrides and not _banned(overrides[oid]):
            line = overrides[oid]
            naming = "override"
        if _banned(line):
            line = template
            naming = "template"
        sources = {m.source for m in cluster.members if m.source}
        out.append(
            NamedOpportunity(
                opportunity_id=oid,
                problem_one_liner=line,
                member_doc_ids=[m.doc_id for m in cluster.members],
                representative_doc_ids=[r["doc_id"] for r in reps],
                job_mix=job_mix,
                blocker_mix=blocker_mix,
                source_mix=source_mix,
                single_source_warning=len(sources) < 2,
                quotes=quotes,
                naming_source=naming,
                cluster_version=config.cluster.version,
            )
        )
    out.sort(key=lambda o: (-len(o.member_doc_ids), o.opportunity_id))
    return out


def pick_representatives(
    cluster: Cluster,
    limit: int = 6,
    *,
    job_mix: dict[str, float] | None = None,
    blocker_mix: dict[str, float] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    topic_jobs = [k for k, v in (job_mix or {}).items() if v and k != "unknown"]
    topic_blockers = [k for k, v in (blocker_mix or {}).items() if v]
    members = [
        m
        for m in cluster.members
        if quote_is_relevant(
            m.evidence_span or m.text[:180],
            jobs=m.jobs or topic_jobs,
            blockers=m.blockers or topic_blockers,
            full_text=m.text,
        )
    ]
    if not members:
        return [], []

    grouped: dict[str, list[Member]] = {}
    for member in members:
        grouped.setdefault(member.source or "unknown", []).append(member)
    for source in grouped:
        grouped[source].sort(key=lambda m: m.observed_at or "", reverse=True)
    reps: list[Member] = []
    sources = sorted(grouped)
    idx = 0
    while len(reps) < limit and any(grouped[s] for s in sources):
        source = sources[idx % len(sources)]
        idx += 1
        if grouped[source]:
            reps.append(grouped[source].pop(0))
    quotes = []
    for member in reps:
        quote = member.evidence_span if member.evidence_span and member.evidence_span in member.text else ""
        if not quote or not quote_is_relevant(
            quote,
            jobs=member.jobs or topic_jobs,
            blockers=member.blockers or topic_blockers,
            full_text=member.text,
        ):
            quote = ""
        if not quote and member.text:
            mined = extract_relevant_snippet(
                member.text,
                jobs=member.jobs or topic_jobs,
                blockers=member.blockers or topic_blockers,
            )
            if mined:
                quote = mined
            else:
                claim_span = member.evidence_span if member.evidence_span in member.text else member.text[:180]
                if quote_is_relevant(
                    claim_span,
                    jobs=member.jobs or topic_jobs,
                    blockers=member.blockers or topic_blockers,
                    full_text=member.text,
                ):
                    quote = claim_span
        if not quote:
            continue
        quotes.append(
            {
                "doc_id": member.doc_id,
                "source": member.source,
                "observed_at": member.observed_at or "",
                "quote": quote,
            }
        )
    return (
        [{"doc_id": m.doc_id, "source": m.source, "observed_at": m.observed_at or ""} for m in reps],
        quotes,
    )


def _banned(text: str) -> bool:
    lower = (text or "").lower()
    if "miscellaneous" in lower or "quality and price" in lower:
        return True
    return bool(re.search(r"\b(misc|other)\b", lower))
