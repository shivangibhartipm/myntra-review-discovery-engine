"""Agglomerative clustering plus merge/split so clusters stay PM-interpretable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from review_engine.cluster.embed import cosine, mean_vector

SALE_JOBS = {"wait_for_sale"}
SALE_BLOCKERS = {"sale_timing", "price"}
DELIVERY_BLOCKERS = {"delivery_checkout_saved"}
SIZE_BLOCKERS = {"fit", "size_chart"}
JOB_PRIORITY = (
    "wait_for_sale",
    "shortlist_compare",
    "intent_blocked",
    "occasion_social",
    "impulse_park",
    "bookmark_later",
    "unknown",
)
BLOCKER_PRIORITY = (
    "delivery_checkout_saved",
    "size_chart",
    "sale_timing",
    "photo_mismatch",
    "authenticity",
    "competitor_check",
    "review_volume_trust",
    "returns",
    "styling_occasion",
    "social_validation",
    "fabric_quality",
    "fit",
    "price",
)


@dataclass
class Member:
    doc_id: str
    source: str
    observed_at: str | None
    text: str
    jobs: list[str]
    blockers: list[str]
    evidence_span: str
    postponement: str
    vector: list[float]

    def primary_job(self) -> str:
        for job in JOB_PRIORITY:
            if job in self.jobs:
                return job
        return "unknown"

    def primary_blocker(self) -> str | None:
        for blocker in BLOCKER_PRIORITY:
            if blocker in self.blockers:
                return blocker
        return self.blockers[0] if self.blockers else None


@dataclass
class Cluster:
    label: str
    members: list[Member] = field(default_factory=list)

    @property
    def centroid(self) -> list[float]:
        return mean_vector([m.vector for m in self.members if m.vector])

    def job_values(self) -> list[str]:
        return [m.primary_job() for m in self.members]

    def blocker_values(self) -> list[str]:
        return [b for m in self.members if (b := m.primary_blocker())]

    def sources(self) -> list[str]:
        return [m.source for m in self.members]


def agglomerative_cluster(members: list[Member], k: int) -> list[Cluster]:
    if not members:
        return []
    k = max(1, min(k, len(members)))
    clusters = [Cluster(label=str(i), members=[m]) for i, m in enumerate(members)]
    while len(clusters) > k:
        best_i, best_j, best_sim = 0, 1, -2.0
        for i in range(len(clusters)):
            ci = clusters[i].centroid
            for j in range(i + 1, len(clusters)):
                sim = cosine(ci, clusters[j].centroid)
                if sim > best_sim:
                    best_i, best_j, best_sim = i, j, sim
        merged = Cluster(
            label=clusters[best_i].label,
            members=clusters[best_i].members + clusters[best_j].members,
        )
        clusters = [c for n, c in enumerate(clusters) if n not in {best_i, best_j}]
        clusters.append(merged)
    return clusters


def target_k(n: int, min_k: int, max_k: int) -> int:
    if n <= 1:
        return n
    guessed = max(min_k, min(max_k, max(2, n // 3)))
    return max(1, min(n, guessed, max_k))


def split_mixed_clusters(clusters: list[Cluster]) -> list[Cluster]:
    out: list[Cluster] = []
    for cluster in clusters:
        sale, delivery = _axis_shares(cluster)
        if sale >= 0.25 and delivery >= 0.25 and len(cluster.members) >= 2:
            sale_m, del_m = [], []
            for member in cluster.members:
                if _on_delivery(member) and not _on_sale(member):
                    del_m.append(member)
                elif _on_sale(member) and not _on_delivery(member):
                    sale_m.append(member)
                elif _on_delivery(member):
                    del_m.append(member)
                elif _on_sale(member):
                    sale_m.append(member)
                else:
                    (sale_m if sale >= delivery else del_m).append(member)
            if sale_m and del_m:
                out.append(Cluster(label=cluster.label + "_sale", members=sale_m))
                out.append(Cluster(label=cluster.label + "_delivery", members=del_m))
                continue
        out.append(cluster)
    return _split_blocker_families(out)


def _blocker_key(member: Member) -> str:
    blocker = member.primary_blocker()
    if blocker in SIZE_BLOCKERS:
        return "size"
    return blocker or "none"


def _split_blocker_families(clusters: list[Cluster]) -> list[Cluster]:
    """Split clusters that mixed distinct blockers (size vs authenticity vs delivery)."""
    out: list[Cluster] = []
    for cluster in clusters:
        buckets: dict[str, list[Member]] = {}
        for member in cluster.members:
            buckets.setdefault(_blocker_key(member), []).append(member)
        large = {key: members for key, members in buckets.items() if len(members) >= 2}
        if len(large) < 2:
            out.append(cluster)
            continue
        parts: list[Cluster] = []
        for key, members in large.items():
            parts.append(Cluster(label=f"{cluster.label}_{key}", members=list(members)))
        leftover = [m for key, members in buckets.items() if len(members) < 2 for m in members]
        for member in leftover:
            best = max(parts, key=lambda c: cosine(member.vector, c.centroid))
            best.members.append(member)
        out.extend(parts)
    return out


def merge_duplicates(clusters: list[Cluster], merge_cosine: float, max_k: int) -> list[Cluster]:
    del merge_cosine
    clusters = [c for c in clusters if c.members]
    changed = True
    while changed and len(clusters) > 1:
        changed = False
        best: tuple[int, int, float] | None = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                if _duplicate_theme(clusters[i], clusters[j]):
                    sim = cosine(clusters[i].centroid, clusters[j].centroid)
                    if best is None or sim > best[2]:
                        best = (i, j, sim)
        if best is None:
            break
        i, j, _ = best
        merged = Cluster(
            label=clusters[i].label,
            members=clusters[i].members + clusters[j].members,
        )
        clusters = [c for n, c in enumerate(clusters) if n not in {i, j}]
        clusters.append(merged)
        changed = True
    while len(clusters) > max_k:
        best_i, best_j, best_sim = 0, 1, -2.0
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                sim = cosine(clusters[i].centroid, clusters[j].centroid)
                if sim > best_sim:
                    best_i, best_j, best_sim = i, j, sim
        merged = Cluster(
            label=clusters[best_i].label,
            members=clusters[best_i].members + clusters[best_j].members,
        )
        clusters = [c for n, c in enumerate(clusters) if n not in {best_i, best_j}]
        clusters.append(merged)
    return clusters


def reassign_tiny(clusters: list[Cluster], min_size: int) -> list[Cluster]:
    kept = [c for c in clusters if len(c.members) >= min_size]
    tiny = [c for c in clusters if len(c.members) < min_size]
    if not kept:
        return [c for c in clusters if c.members]
    for orphan in tiny:
        for member in orphan.members:
            best = max(kept, key=lambda c: cosine(member.vector, c.centroid))
            best.members.append(member)
    return [c for c in kept if c.members]


def expand_if_too_few(clusters: list[Cluster], members: list[Member], min_k: int, max_k: int) -> list[Cluster]:
    if len(clusters) >= min_k or len(members) < min_k:
        return clusters
    largest = max(clusters, key=lambda c: len(c.members))
    if len(largest.members) < 4:
        return clusters
    if max_k - len(clusters) + 1 < 2:
        return clusters
    parts = agglomerative_cluster(largest.members, 2)
    rest = [c for c in clusters if c is not largest]
    return rest + parts


def _duplicate_theme(a: Cluster, b: Cluster) -> bool:
    if _same_theme(a, b):
        return True
    return _size_family(a) and _size_family(b)


def _top(values: Sequence[str]) -> str | None:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _same_theme(a: Cluster, b: Cluster) -> bool:
    return (
        _top(a.job_values()) == _top(b.job_values())
        and _top(a.blocker_values()) == _top(b.blocker_values())
        and _top(a.job_values()) is not None
    )


def _size_family(cluster: Cluster) -> bool:
    blockers = set(cluster.blocker_values())
    jobs = set(cluster.job_values())
    return bool(blockers & SIZE_BLOCKERS) and not (jobs & SALE_JOBS)


def _on_sale(member: Member) -> bool:
    return bool(set(member.jobs) & SALE_JOBS) or bool(set(member.blockers) & SALE_BLOCKERS)


def _on_delivery(member: Member) -> bool:
    return bool(set(member.blockers) & DELIVERY_BLOCKERS)


def _axis_shares(cluster: Cluster) -> tuple[float, float]:
    n = len(cluster.members) or 1
    sale = sum(1 for m in cluster.members if _on_sale(m)) / n
    delivery = sum(1 for m in cluster.members if _on_delivery(m)) / n
    return sale, delivery


agglomerative_cluster = agglomerative_cluster
expand_if_too_few = expand_if_too_few
merge_duplicates = merge_duplicates
reassign_tiny = reassign_tiny
