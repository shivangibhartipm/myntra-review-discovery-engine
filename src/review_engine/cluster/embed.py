from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Sequence

from review_engine.extract.taxonomy import BLOCKERS, JOBS
from review_engine.ollama_client import OllamaError, embed_text

TAG_DIM = len(JOBS) + len(BLOCKERS) + 3  # postpone yes/no/unknown
HASH_DIM = 24


def claim_embed_text(
    *,
    text: str,
    jobs: Sequence[str],
    blockers: Sequence[str],
    evidence_span: str,
) -> str:
    return (
        f"jobs={' '.join(jobs)} blockers={' '.join(blockers)} "
        f"quote={evidence_span or ''} text={(text or '')[:400]}"
    )


def tag_vector(
    *,
    jobs: Sequence[str],
    blockers: Sequence[str],
    postponement: str,
    text: str,
) -> list[float]:
    vec = [0.0] * (TAG_DIM + HASH_DIM)
    for i, job in enumerate(JOBS):
        if job in jobs:
            vec[i] = 1.0
    offset = len(JOBS)
    for i, blocker in enumerate(BLOCKERS):
        if blocker in blockers:
            vec[offset + i] = 1.0
    postpone_idx = {"yes": 0, "no": 1, "unknown": 2}.get(postponement, 2)
    vec[len(JOBS) + len(BLOCKERS) + postpone_idx] = 1.0
    body = (text or "").lower()
    for token in body.split():
        token = token.strip(".,!?;:\"'")
        if len(token) < 4:
            continue
        digest = hashlib.md5(token.encode("utf-8")).digest()
        idx = digest[0] % HASH_DIM
        vec[TAG_DIM + idx] += 0.05
    return l2_normalize(vec)


def concat_vectors(tag: list[float], dense: list[float] | None, *, tag_weight: float = 2.0) -> list[float]:
    weighted = [tag_weight * x for x in tag]
    if not dense:
        return l2_normalize(weighted)
    return l2_normalize(weighted + l2_normalize(dense))


def l2_normalize(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return list(vec)
    return [x / norm for x in vec]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def mean_vector(vectors: Sequence[Sequence[float]]) -> list[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    acc = [0.0] * dim
    for vec in vectors:
        for i, x in enumerate(vec):
            acc[i] += x
    n = float(len(vectors))
    return l2_normalize([x / n for x in acc])


def parse_stored_embedding(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(value, list) and value and isinstance(value[0], (int, float)):
        return [float(x) for x in value]
    return None


def dense_embed(text: str, *, host: str, model: str) -> list[float] | None:
    try:
        return embed_text(host=host, model=model, text=text[:8000])
    except OllamaError:
        return None


def histogram(values: Sequence[str]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for value in values:
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    total = sum(counts.values()) or 1
    return {k: round(v / total, 4) for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))}


def parse_json_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return [raw] if raw else []
        if isinstance(value, list):
            return [str(x) for x in value if x]
    return []


mean_vector = mean_vector
