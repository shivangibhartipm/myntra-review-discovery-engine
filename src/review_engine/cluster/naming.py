from __future__ import annotations

import json
import re
from pathlib import Path

from review_engine.cluster.embed import histogram
from review_engine.cluster.group import Cluster
from review_engine.config import AppConfig
from review_engine.ollama_client import OllamaError, generate_json

JOB_COPY = {
    "bookmark_later": "save items as bookmarks instead of buying now",
    "wait_for_sale": "wait for a sale or price drop before buying saved items",
    "shortlist_compare": "delay while comparing shortlisted products",
    "intent_blocked": "want the item but a concrete blocker stops checkout",
    "occasion_social": "wait for occasion or social confidence before buying a saved look",
    "impulse_park": "park items they liked in a photo with little purchase intent",
}

BLOCKER_COPY = {
    "fit": "they are unsure about size or fit before ordering a saved item",
    "size_chart": "the size chart is unclear for a saved item",
    "photo_mismatch": "the product looks different than photos or haul videos",
    "fabric_quality": "fabric or quality feels uncertain before they commit to a saved item",
    "price": "the current price feels too high",
    "sale_timing": "they are waiting for sale timing (for example EORS)",
    "review_volume_trust": "reviews are too few or untrusted",
    "authenticity": "they worry the item may be fake",
    "returns": "they worry returns won't be easy before ordering a saved item",
    "delivery_checkout_saved": "checkout or delivery fails on a saved item",
    "styling_occasion": "they are unsure it will work for the occasion",
    "social_validation": "they want a friend or social check first",
    "competitor_check": "they are checking a competitor before committing",
}

PROMPT = """Name one fashion-shopping opportunity area for a Growth PM.

Write ONE sentence: the user problem (why a wishlisted item is not bought within 30 days).
Do not use the word miscellaneous. Do not write generic 'quality and price' summaries.
Ground the sentence in the job/blocker mix and quotes.

Return JSON: {{"problem_one_liner":"..."}}

Job mix: {jobs}
Blocker mix: {blockers}
Quotes:
{quotes}
"""


def top_key(mix: dict[str, float]) -> str | None:
    if not mix:
        return None
    return max(mix.items(), key=lambda kv: (kv[1], kv[0]))[0]


def template_one_liner(cluster: Cluster) -> str:
    jobs = histogram(cluster.job_values())
    blockers = histogram(cluster.blocker_values())
    job = top_key(jobs)
    blocker = top_key(blockers)
    job_bit = JOB_COPY.get(job or "", "hesitate on a saved item")
    if blocker and blocker in BLOCKER_COPY:
        return f"Users {job_bit} because {BLOCKER_COPY[blocker]}."
    return f"Users {job_bit}."


def opportunity_id(job: str | None, blocker: str | None, used: set[str]) -> str:
    base = slugify(f"{job or 'theme'}_{blocker or 'open'}")
    candidate = base
    n = 2
    while candidate in used:
        candidate = f"{base}_{n}"
        n += 1
    used.add(candidate)
    return candidate


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return (slug or "opportunity")[:60]


def llm_one_liner(cluster: Cluster, config: AppConfig, quotes: list[str]) -> str | None:
    prompt = PROMPT.format(
        jobs=json.dumps(histogram(cluster.job_values())),
        blockers=json.dumps(histogram(cluster.blocker_values())),
        quotes="\n".join(f"- {q}" for q in quotes[:8]),
    )
    try:
        data = generate_json(host=config.models.ollama_host, model=config.models.generate, prompt=prompt)
    except OllamaError:
        return None
    line = str(data.get("problem_one_liner") or "").strip()
    if not line or "miscellaneous" in line.lower():
        return None
    if line[-1] not in ".!?":
        line += "."
    return line[:240]


def load_overrides(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if v}
