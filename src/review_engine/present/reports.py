from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping

from review_engine.present.briefing import briefing_markdown, build_briefing
from review_engine.present.plain import (
    blocks_purchase_ever,
    delay_strength,
    how_common,
    waiting_past_30d,
)


FORBIDDEN_HERO = ("nps", "net promoter", "topic cloud", "star rating")


def ranked_markdown(
    opportunities: list[Mapping[str, Any]],
    *,
    windows: Mapping[str, Any] | None = None,
    corpus_health: Mapping[str, Any] | None = None,
    message: str | None = None,
    briefing: Mapping[str, Any] | None = None,
) -> str:
    brief = briefing or build_briefing(opportunities)
    lines = briefing_markdown(brief)
    lines.extend(
        [
            "## Ranked bets (90-day conversion view, not mention volume)",
            "",
        ]
    )
    if message:
        lines.extend([message, ""])
    if windows:
        lines.extend(
            [
                f"- As of: `{windows.get('as_of', '')}`",
                f"- Recency start: `{windows.get('recency_start', '')}`",
                f"- Primary start: `{windows.get('primary_start', '')}`",
                "",
            ]
        )
    if not opportunities:
        lines.append("No ranked opportunities. Run `--phase rank` first.")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| Conversion rank | Volume rank | User problem | Within 30 days | Ever blocks buy | How common | Waiting past 30 days |",
            "| ---: | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in sorted(opportunities, key=lambda o: o.get("rank_90d") or 10**9):
        lines.append(
            "| {rank} | {vol} | {name} | {mr} | {ever} | {prev} | {post} |".format(
                rank=row.get("rank_90d") or "",
                vol=row.get("volume_rank") or "",
                name=_pipe(str(row.get("problem_one_liner") or row.get("opportunity_id"))),
                mr=_pipe(delay_strength(row.get("metric_relevance"))),
                ever=_pipe(blocks_purchase_ever(row.get("metric_relevance"))),
                prev=_pipe(how_common(row.get("prevalence_relevant"))),
                post=_pipe(waiting_past_30d(row.get("postponement_rate"))),
            )
        )
    lines.append("")

    for row in sorted(opportunities, key=lambda o: o.get("rank_90d") or 10**9):
        lines.extend(_opportunity_section(row))

    if corpus_health:
        lines.extend(["## Corpus health (trust, not the ranking)", ""])
        lines.append(
            f"- Collected: {corpus_health.get('n_unfiltered')} · Relevant: {corpus_health.get('n_relevant')}"
        )
        last = corpus_health.get("last_run") or {}
        if last:
            lines.append(
                f"- Last pipeline run: `{last.get('phase', '')}` at `{last.get('started_at', '')}`"
            )
        lines.append("")

    text = "\n".join(lines) + "\n"
    lowered = text.lower()
    for token in FORBIDDEN_HERO:
        if lowered.startswith(token):
            raise ValueError(f"report must not lead with {token}")
    return text


def _opportunity_section(row: Mapping[str, Any]) -> list[str]:
    oid = row.get("opportunity_id")
    lines = [
        f"### {row.get('rank_90d') or '-'}. {row.get('problem_one_liner') or oid}",
        "",
        f"- Id: `{oid}`",
        f"- How it delays conversion: {row.get('delay_mechanism') or 'See quotes.'}",
        f"- Within 30 days: {delay_strength(row.get('metric_relevance'))}",
        f"- Wishlist → purchase (in general): {blocks_purchase_ever(row.get('metric_relevance'))}",
        f"- How common: {how_common(row.get('prevalence_relevant'))}",
        f"- Waiting past 30 days: {waiting_past_30d(row.get('postponement_rate'))}",
        f"- Source mix: {_fmt_mix(row.get('source_mix'))}",
        f"- Job mix: {_fmt_mix(row.get('job_mix'))} · Blocker mix: {_fmt_mix(row.get('blocker_mix'))}",
        f"- Suggested lever (hypothesis only): {row.get('suggested_lever')}",
    ]
    if row.get("comparison_notes"):
        lines.append(f"- vs next theme: {row['comparison_notes']}")
    lines.append("")
    quotes = row.get("quotes") or []
    if quotes:
        lines.append("Quotes:")
        for q in quotes:
            lines.append(
                f"- `{q.get('source')}` `{q.get('observed_at')}` `{q.get('doc_id')}`: {_pipe(str(q.get('quote') or ''))}"
            )
        lines.append("")
    return lines


def onepager_markdown(row: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            f"# {row.get('problem_one_liner') or row.get('opportunity_id')}",
            "",
            "One-pager for wishlist → purchase (within 30 days and overall). Hypothesis only — not a committed roadmap.",
            "",
            *_opportunity_section(row),
        ]
    )


def write_csv(path: Path, opportunities: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank_90d",
        "rank_12m",
        "volume_rank",
        "opportunity_id",
        "problem_one_liner",
        "metric_relevance",
        "prevalence_relevant",
        "prevalence_unfiltered",
        "postponement_rate",
        "recency_90d_share",
        "actionability",
        "delay_mechanism",
        "suggested_lever",
        "source_mix",
        "job_mix",
        "blocker_mix",
        "comparison_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(opportunities, key=lambda o: o.get("rank_90d") or 10**9):
            writer.writerow(
                {
                    **{k: row.get(k) for k in fieldnames},
                    "source_mix": _fmt_mix(row.get("source_mix")),
                    "job_mix": _fmt_mix(row.get("job_mix")),
                    "blocker_mix": _fmt_mix(row.get("blocker_mix")),
                }
            )


def _fmt_mix(mix: Any) -> str:
    if not isinstance(mix, dict) or not mix:
        return ""
    return "; ".join(f"{k}:{v}" for k, v in mix.items())


def _pipe(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")
