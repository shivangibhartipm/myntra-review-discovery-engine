"""Grounded answers to the problem-statement discovery questions.

Built from ranked opportunity mixes and quotes — not sentiment, not an ungrounded summary.
Covers two conversion horizons: wishlist→purchase in general, and within 30 days of save.
"""

from __future__ import annotations

from typing import Any, Mapping

from review_engine.present.plain import (
    ROLE_BLOCKERS,
    blocker_label,
    blocks_purchase_ever,
    delay_strength,
    how_common,
    job_label,
    pct,
    waiting_past_30d,
)
from review_engine.present.segments import (
    attach_opportunity_ids,
    demographic_segments_from_db,
)
from review_engine.present.wishlist_signals import WishlistSignalReport, merge_job_reasons

# (id, question, scenario) — scenario is "general", "within_30d", or "both"
QUESTIONS: tuple[tuple[str, str, str], ...] = (
    ("why_wishlist", "Why do users add fashion products to their wishlist?", "both"),
    (
        "stops_purchase",
        "What prevents wishlisted products from being purchased, and what uncertainties remain after users like an item?",
        "general",
    ),
    ("postpone_30d", "What causes users to postpone a purchase?", "within_30d"),
    ("compare_shortlist", "How do users compare multiple shortlisted products?", "both"),
    ("outside_myntra", "What information do users seek outside Myntra before purchasing?", "both"),
    (
        "roles",
        "What role do fit, size, styling, price, reviews, occasion and social validation play?",
        "both",
    ),
    (
        "intent_vs_bookmark",
        "When do users use the wishlist as genuine purchase intent versus simply as a bookmarking mechanism?",
        "both",
    ),
    ("wishlist_frequency", "How often do users add products to their wishlist?", "both"),
    (
        "wishlist_conversion",
        "How often do users buy products from their wishlist?",
        "both",
    ),
    ("segments", "How do these behaviors differ across user segments?", "both"),
    ("loud_vs_metric", "What unmet needs emerge consistently across user conversations?", "both"),
)

_UNCERTAIN = {"fit", "size_chart", "photo_mismatch", "fabric_quality", "review_volume_trust"}
_OUTSIDE = {"competitor_check", "social_validation", "photo_mismatch"}


def build_briefing(
    opportunities: list[Mapping[str, Any]],
    *,
    demographic_segments: list[Mapping[str, Any]] | None = None,
    wishlist_signals: WishlistSignalReport | None = None,
) -> dict[str, Any]:
    ranked = sorted(opportunities, key=lambda o: (o.get("rank_90d") is None, o.get("rank_90d") or 10**9))
    job_w = _weighted_mix(ranked, "job_mix")
    blocker_w = _weighted_mix(ranked, "blocker_mix")
    intent = _weighted_intent(ranked)
    demo = [dict(s) for s in (demographic_segments or demographic_segments_from_db())]
    if demo:
        demo = attach_opportunity_ids(demo, [dict(o) for o in ranked])
    questions = [
        _answer(
            qid, question, scenario, ranked, job_w, blocker_w, intent, demo, wishlist_signals
        )
        for qid, question, scenario in QUESTIONS
    ]
    signals = (wishlist_signals or WishlistSignalReport()).as_dict()
    first = ranked[0] if ranked else None
    return {
        "goal": (
            "Help more people buy at least one saved item — both eventually "
            "(wishlist → purchase in general) and within a month of saving it. "
            "Not a star-rating summary."
        ),
        "first_bet": _first_bet(first) if first else None,
        "scenarios": _scenarios(ranked, job_w, blocker_w),
        "demographic_segments": demo,
        "wishlist_signals": signals,
        "questions": questions,
    }


def briefing_markdown(briefing: Mapping[str, Any]) -> list[str]:
    lines = [
        "# Wishlist → purchase: within 30 days and overall",
        "",
        str(briefing.get("goal") or ""),
        "",
        "These answers cover two horizons: what stops a saved item from becoming an order at all, "
        "and what pushes the buy past a month — not star ratings.",
        "",
    ]
    for sc in briefing.get("scenarios") or []:
        lines.extend(
            [
                f"## Scenario · {sc.get('title')}",
                "",
                str(sc.get("summary") or ""),
                "",
            ]
        )
        for ev in sc.get("evidence") or []:
            lines.append(f"- {ev}")
        if sc.get("evidence"):
            lines.append("")
    first = briefing.get("first_bet")
    if first:
        lines.extend(
            [
                "## Test this first",
                "",
                f"**{first.get('problem')}**",
                "",
                first.get("why") or "",
                "",
                f"Idea to try: {first.get('lever')}",
                "",
            ]
        )
        if first.get("quote"):
            lines.extend([f"> {first['quote']}", ""])
    lines.extend(["## Discovery questions", ""])
    for item in briefing.get("questions") or []:
        label = _scenario_label(str(item.get("scenario") or "both"))
        lines.append(f"### {item.get('question')}")
        lines.append("")
        lines.append(f"*Horizon: {label}*")
        lines.append("")
        lines.append(str(item.get("answer") or ""))
        lines.append("")
        for ev in item.get("evidence") or []:
            lines.append(f"- {ev}")
        if item.get("evidence"):
            lines.append("")
    return lines


def _first_bet(row: Mapping[str, Any]) -> dict[str, Any]:
    quote = ""
    quotes = row.get("quotes") or []
    if quotes and isinstance(quotes[0], dict):
        quote = str(quotes[0].get("quote") or "")
    return {
        "opportunity_id": row.get("opportunity_id"),
        "problem": row.get("problem_one_liner"),
        "why": row.get("delay_mechanism"),
        "lever": row.get("suggested_lever"),
        "quote": quote,
        "delay_strength": delay_strength(row.get("metric_relevance")),
        "blocks_purchase_ever": blocks_purchase_ever(row.get("metric_relevance")),
        "how_common": how_common(row.get("prevalence_relevant")),
        "waiting_past_30d": waiting_past_30d(row.get("postponement_rate")),
    }


def _scenarios(
    ranked: list[Mapping[str, Any]],
    job_w: dict[str, float],
    blocker_w: dict[str, float],
) -> list[dict[str, Any]]:
    if not ranked:
        return [
            {
                "id": "general",
                "title": "Wishlist → purchase (in general)",
                "summary": "We don’t have enough comments yet to explain why saved items never become orders.",
                "evidence": [],
                "opportunity_ids": [],
            },
            {
                "id": "within_30d",
                "title": "Within 30 days of saving",
                "summary": "We don’t have enough comments yet to explain why buys slip past a month.",
                "evidence": [],
                "opportunity_ids": [],
            },
        ]

    general_leaders = sorted(
        ranked,
        key=lambda o: (
            -float(o.get("metric_relevance") or 0),
            -float(o.get("prevalence_relevant") or 0),
            o.get("rank_90d") or 99,
        ),
    )
    # Prefer themes that block the buy even when they are not calendar postponements.
    general_focus = [
        o
        for o in general_leaders
        if float(o.get("postponement_rate") or 0) < 0.3 or float(o.get("prevalence_relevant") or 0) >= 0.1
    ] or general_leaders
    top_blockers = _top_keys(blocker_w, 3)
    general_summary = (
        "Wishlist → purchase in general fails when shoppers hit blockers after saving — "
        + (
            _join([blocker_label(k) for k in top_blockers])
            if top_blockers
            else "mixed reasons in the comments"
        )
        + ". This is about ever converting a saved item, not only the 30-day clock."
    )
    general_evidence = [
        f"{o.get('problem_one_liner')} — {blocks_purchase_ever(o.get('metric_relevance'))}"
        for o in general_focus[:3]
    ]
    if top_blockers:
        general_evidence.extend(
            [f"{blocker_label(k)}: {pct(blocker_w[k])} of comments about this" for k in top_blockers[:2]]
        )

    waiting = sorted(
        ranked,
        key=lambda o: (-float(o.get("postponement_rate") or 0), o.get("rank_90d") or 99),
    )
    strong_wait = [o for o in waiting if float(o.get("postponement_rate") or 0) >= 0.3]
    if strong_wait:
        lead = strong_wait[0]
        within_summary = (
            f"Within 30 days of saving, the buy most often slips because: {lead.get('problem_one_liner')} "
            f"{waiting_past_30d(lead.get('postponement_rate'))}."
        )
        within_evidence = [
            f"{o.get('problem_one_liner')} — {waiting_past_30d(o.get('postponement_rate'))}"
            for o in strong_wait[:3]
        ]
        within_ids = [str(o.get("opportunity_id")) for o in strong_wait[:3]]
    else:
        within_summary = (
            "Few snippets are tagged as delaying past 30 days. Sale-wait and salary/bookmark language "
            "is the usual clock when it does appear — use the ranked list for near-term conversion bets."
        )
        within_evidence = [
            f"{ranked[0].get('problem_one_liner')} — {delay_strength(ranked[0].get('metric_relevance'))}"
        ]
        within_ids = [str(ranked[0].get("opportunity_id"))]

    wait_job = job_w.get("wait_for_sale", 0.0)
    if wait_job > 0:
        within_evidence.append(f"Waiting for a sale (job share): {pct(wait_job)}")

    return [
        {
            "id": "general",
            "title": "Wishlist → purchase (in general)",
            "summary": general_summary,
            "evidence": general_evidence,
            "opportunity_ids": [str(o.get("opportunity_id")) for o in general_focus[:3]],
        },
        {
            "id": "within_30d",
            "title": "Within 30 days of saving",
            "summary": within_summary,
            "evidence": within_evidence,
            "opportunity_ids": within_ids,
        },
    ]


def _answer(
    qid: str,
    question: str,
    scenario: str,
    ranked: list[Mapping[str, Any]],
    job_w: dict[str, float],
    blocker_w: dict[str, float],
    intent: dict[str, float],
    demographic_segments: list[Mapping[str, Any]] | None = None,
    wishlist_signals: WishlistSignalReport | None = None,
) -> dict[str, Any]:
    if not ranked:
        return {
            "id": qid,
            "question": question,
            "scenario": scenario,
            "answer": "We don’t have enough comments yet to answer this.",
            "evidence": [],
            "opportunity_ids": [],
        }
    if qid == "segments":
        answer, evidence, ids = _segments(ranked, job_w, blocker_w, intent, demographic_segments or [])
    elif qid == "wishlist_frequency":
        answer, evidence, ids = _wishlist_frequency(ranked, job_w, wishlist_signals)
    elif qid == "wishlist_conversion":
        answer, evidence, ids = _wishlist_conversion(ranked, wishlist_signals)
    elif qid == "why_wishlist":
        answer, evidence, ids = _why_wishlist(ranked, job_w, blocker_w, intent, wishlist_signals)
    else:
        fn = {
            "stops_purchase": _stops,
            "postpone_30d": _postpone,
            "compare_shortlist": _compare,
            "outside_myntra": _outside,
            "roles": _roles,
            "intent_vs_bookmark": _intent,
            "loud_vs_metric": _loud,
        }[qid]
        answer, evidence, ids = fn(ranked, job_w, blocker_w, intent)
    return {
        "id": qid,
        "question": question,
        "scenario": scenario,
        "answer": answer,
        "evidence": evidence,
        "opportunity_ids": ids,
    }


def _why_wishlist(ranked, job_w, blocker_w, intent, wishlist_signals=None):
    del blocker_w, intent
    signals = wishlist_signals or WishlistSignalReport()
    merged = merge_job_reasons(job_w, signals.add_reasons)
    if merged:
        parts = [label for _, label in merged[:3]]
        answer = (
            "Users mainly add fashion products to their wishlist to "
            + _join(parts)
            + ". These are inferred from save/compare/sale language in comments that mention wishlist or saved items."
        )
        evidence = [f"{label}: seen in wishlist-tagged comments" for _, label in merged[:4]]
        if signals.n_wishlist_language:
            evidence.insert(
                0,
                f"Explicit wishlist/save language in {signals.n_wishlist_language} of {signals.n_corpus} corpus comments",
            )
        ids = _ids_with_job(ranked, merged[0][0]) if merged else []
        return answer, evidence, ids
    top = _top_keys(job_w, 3)
    if not top:
        return (
            "Shopper comments rarely say “wishlist” outright. In this corpus, save behavior shows up indirectly "
            "through waiting for sales, saving for later, and comparing options — not through explicit add-to-wishlist talk."
        ), [], []
    parts = [job_label(k) for k in top]
    answer = (
        "Users mainly add fashion products to their wishlist for "
        + _join(parts)
        + ". In short: they are parking interest — to buy later, wait for a better price, compare options, "
        "or hold something until a doubt is cleared — not leaving a star rating."
    )
    evidence = [f"{job_label(k)}: {pct(job_w[k])} of wishlist-related comments" for k in top]
    ids = _ids_with_job(ranked, top[0])
    return answer, evidence, ids


def _wishlist_frequency(ranked, job_w, wishlist_signals=None):
    del job_w
    signals = wishlist_signals or WishlistSignalReport()
    if signals.n_freq_add:
        answer = (
            f"Some users describe how often they add to wishlist: {signals.n_freq_add} comment(s) mention "
            "frequent or habitual saving (for example “every time”, “often”, or “daily”)."
        )
        evidence = [f"Frequency-add mentions: {signals.n_freq_add}"]
        evidence.extend(signals.freq_add_samples[:3])
        return answer, evidence, [str(ranked[0].get("opportunity_id"))] if ranked else []
    if signals.n_wishlist_language:
        answer = (
            f"This corpus has {signals.n_wishlist_language} comments with explicit wishlist/save language "
            f"out of {signals.n_corpus} total — too few to estimate how often people add items. "
            "App-store reviews rarely describe save frequency; YouTube haul comments and Reddit threads are better sources."
        )
        evidence = [
            f"Wishlist/save language: {signals.n_wishlist_language} comments",
            f"By source: {signals.by_source}",
        ]
        evidence.extend(signals.wishlist_samples[:3])
        return answer, evidence, [str(o.get("opportunity_id")) for o in ranked[:2]]
    return (
        "We do not yet have enough comments that mention adding to a wishlist to estimate how often users save items.",
        [],
        [],
    )


def _wishlist_conversion(ranked, wishlist_signals=None):
    signals = wishlist_signals or WishlistSignalReport()
    if signals.n_freq_buy:
        answer = (
            f"{signals.n_freq_buy} comment(s) describe buying from (or never buying from) a wishlist. "
            "That is not enough to quantify conversion rate, but it shows people do talk about wishlist → purchase gaps."
        )
        evidence = [f"Wishlist-buy mentions: {signals.n_freq_buy}"]
        evidence.extend(signals.freq_buy_samples[:3])
        return answer, evidence, [str(ranked[0].get("opportunity_id"))] if ranked else []
    postpone = sorted(
        ranked,
        key=lambda o: (-float(o.get("postponement_rate") or 0), o.get("rank_90d") or 99),
    )
    strong = [o for o in postpone if float(o.get("postponement_rate") or 0) >= 0.3]
    if strong:
        answer = (
            "Few comments state how often people buy from wishlist. Indirectly, many saved items stay unpurchased: "
            "topics with clear “wait past 30 days” language suggest wishlist items often do not convert quickly."
        )
        evidence = [
            f"{_plain_problem(o)} — {waiting_past_30d(o.get('postponement_rate'))}" for o in strong[:3]
        ]
        return answer, evidence, [str(o.get("opportunity_id")) for o in strong[:3]]
    return (
        "This corpus does not yet include enough comments about buying from a wishlist to estimate conversion frequency. "
        "Collect more YouTube haul / Reddit wishlist threads, or in-app survey data, for a reliable rate.",
        [f"Wishlist-buy mentions in corpus: {signals.n_freq_buy}"],
        [],
    )


def _stops(ranked, job_w, blocker_w, intent):
    del job_w, intent
    top = _top_keys(blocker_w, 4)
    if not top:
        return (
            "We do not yet see clear reasons that stop a wishlisted product from being bought, "
            "or leftover doubts after someone likes an item."
        ), [], []
    uncertain = [k for k in _top_keys(blocker_w, 8) if k in _UNCERTAIN]
    answer = (
        "What usually prevents a wishlisted product from being purchased is "
        + _join([blocker_label(k) for k in top])
        + ". "
    )
    if uncertain:
        answer += (
            "Even after users have found a product they like, leftover uncertainty is mostly "
            + _join([blocker_label(k) for k in uncertain])
            + ". That doubt is often what keeps a saved item from becoming an order."
        )
    else:
        answer += (
            "In this run, leftover doubt after liking an item is less explicit; "
            "other blockers (for example waiting for a sale or price) dominate instead."
        )
    # Chart: blocker shares (covers both purchase blockers and uncertainty tags)
    evidence = [f"{blocker_label(k)}: {pct(blocker_w[k])} of comments about this" for k in top]
    for k in uncertain:
        if k not in top:
            evidence.append(f"{blocker_label(k)}: {pct(blocker_w.get(k, 0))} of comments about this")
    return answer, evidence, _ids_with_blocker(ranked, top[0])


def _postpone(ranked, job_w, blocker_w, intent):
    del blocker_w, intent
    wait_job = float(job_w.get("wait_for_sale", 0.0) or 0.0)
    bookmark = float(job_w.get("bookmark_later", 0.0) or 0.0) + float(job_w.get("impulse_park", 0.0) or 0.0)
    waiting = sorted(
        ranked,
        key=lambda o: (-float(o.get("postponement_rate") or 0), o.get("rank_90d") or 99),
    )
    strong = [o for o in waiting if float(o.get("postponement_rate") or 0) >= 0.3]
    if strong:
        lead = strong[0]
        answer = (
            f"Users most often postpone a purchase because they {_plain_problem(lead)}. "
            f"{waiting_past_30d(lead.get('postponement_rate'))} "
            "Common “I’ll buy later” triggers are sales (for example EORS), price drops, and saving for later on purpose."
        )
        evidence = [
            f"{_plain_problem(o)} — {waiting_past_30d(o.get('postponement_rate'))}"
            for o in strong[:3]
        ]
        if wait_job > 0:
            evidence.append(f"Waiting for a sale shows up in about {pct(wait_job)} of these comments")
        if bookmark > 0:
            evidence.append(f"Saving for later / on impulse: about {pct(bookmark)}")
        return answer, evidence, [str(o.get("opportunity_id")) for o in strong[:3]]

    bits = []
    if wait_job > 0:
        bits.append(f"waiting for a sale ({pct(wait_job)})")
    if bookmark > 0:
        bits.append(f"saving for later ({pct(bookmark)})")
    if bits:
        answer = (
            "Users postpone a purchase mainly by "
            + _join(bits)
            + ". Fewer comments say “I’ll wait more than a month” in so many words, "
            "but sale-wait and bookmark language is the usual delay pattern."
        )
        evidence = bits + [f"Top related topic: {_plain_problem(ranked[0])}"]
        return answer, evidence, [str(ranked[0].get("opportunity_id"))]
    return (
        "Few comments clearly explain why users postpone. When they do, they usually talk about waiting for a sale, "
        "a price drop, or saving the item for later."
    ), [], [str(ranked[0].get("opportunity_id"))]


def _compare(ranked, job_w, blocker_w, intent):
    del blocker_w, intent
    share = job_w.get("shortlist_compare", 0.0)
    ids = _ids_with_job(ranked, "shortlist_compare")
    if share < 0.05 and not ids:
        return (
            f"Users rarely describe comparing several shortlisted products side by side here "
            f"(about {pct(share)} of comments). More often they wait, get stuck, or save for later — "
            "not pick between two looks."
        ), [f"Share of people comparing options: {pct(share)}"], []
    answer = (
        f"When users compare shortlisted products (about {pct(share)} of comments), they usually ask "
        "“which of these?”, check Myntra against another store, or wait until size or price feels clearer. "
        "That back-and-forth can delay or block the buy."
    )
    return answer, [f"Share of people comparing options: {pct(share)}"], ids


def _outside(ranked, job_w, blocker_w, intent):
    del job_w, intent
    keys = [k for k in _top_keys(blocker_w, 8) if k in _OUTSIDE]
    sources = _source_share(ranked)
    outside_src = {k: v for k, v in sources.items() if k in {"reddit", "youtube"}}
    if not keys and not outside_src:
        answer = (
            "Most of this feedback is app-store reviews, so we see less about what people check outside Myntra. "
            "In real shopping journeys, users often look at haul videos, Reddit/community threads, "
            "and competitor sites for size, look-in-real-life, and price."
        )
        return answer, [f"Sources in these themes: {_fmt_share(sources)}"], []
    bits = [blocker_label(k) for k in keys] if keys else ["haul videos and community threads"]
    answer = (
        "Before purchasing, users look outside Myntra for "
        + _join(bits)
        + ". Typical checks: competitor price or size, photos vs real product, and friends’ or haul-video opinions."
    )
    evidence = [f"{blocker_label(k)}: {pct(blocker_w.get(k, 0))}" for k in keys]
    if outside_src:
        evidence.append("Community sources in themes: " + _fmt_share(outside_src))
    ids = _ids_with_blocker(ranked, keys[0]) if keys else []
    return answer, evidence, ids


def _roles(ranked, job_w, blocker_w, intent):
    del ranked, intent
    lines = []
    for role, keys in ROLE_BLOCKERS.items():
        label = "styling" if role == "styling" else ("social validation" if role == "social validation" else role)
        if role == "occasion":
            share = sum(blocker_w.get(k, 0.0) for k in ("styling_occasion",)) + job_w.get("occasion_social", 0.0)
        else:
            share = sum(blocker_w.get(k, 0.0) for k in keys)
        if share <= 0:
            lines.append(f"{label}: little clear talk in these comments")
        else:
            lines.append(f"{label}: about {pct(share)} of comments about this")
    answer = (
        "Fit, size, styling, price, reviews, occasion, and social validation each act as either a reason to save "
        "or a reason not to buy yet. Price, sales, and fit usually matter most for whether a saved item gets bought; "
        "generic quality talk can be loud without being the main conversion blocker."
    )
    return answer, lines, []


def _intent(ranked, job_w, blocker_w, intent):
    del blocker_w
    blocked = job_w.get("intent_blocked", 0.0)
    bookmark = job_w.get("bookmark_later", 0.0) + job_w.get("impulse_park", 0.0)
    if intent:
        blocked = max(blocked, intent.get("intent_blocked", 0.0))
        bookmark = max(bookmark, intent.get("bookmark_or_impulse", 0.0))
    wait = job_w.get("wait_for_sale", 0.0)
    answer = (
        f"Genuine purchase intent shows up when someone wants the item but gets stuck "
        f"(about {pct(blocked)} of these comments). "
        f"Bookmarking shows up when they are saving for later or on impulse (about {pct(bookmark)}). "
        f"Waiting for a sale (about {pct(wait)}) is still real interest — they plan to buy, just not at today’s price. "
        "A negative review is not the same as “I want this but can’t check out yet.”"
    )
    evidence = [
        f"Want it but stuck: {pct(job_w.get('intent_blocked', 0.0))}",
        f"Saving for later: {pct(job_w.get('bookmark_later', 0.0))}",
        f"Saving on impulse: {pct(job_w.get('impulse_park', 0.0))}",
        f"Waiting for a sale: {pct(wait)}",
    ]
    ids = list(dict.fromkeys(_ids_with_job(ranked, "intent_blocked") + _ids_with_job(ranked, "bookmark_later")))
    return answer, evidence, ids[:4]


_PRICE_SEGMENT_IDS = frozenset({"deal_hunters", "budget_salary"})
_TRUST_SEGMENT_IDS = frozenset({"first_time", "genz_youth", "parents"})
_LOYALTY_SEGMENT_ID = "repeat_shoppers"


def _segment_group_share(segments: list[Mapping[str, Any]]) -> float:
    return sum(float(s.get("share") or 0) for s in segments)


def _segment_answer_narrative(top: list[Mapping[str, Any]]) -> str:
    """Readable segment summary grouped by what drives each shopper type to wait."""
    price = [s for s in top if s.get("id") in _PRICE_SEGMENT_IDS]
    trust = [s for s in top if s.get("id") in _TRUST_SEGMENT_IDS]
    occasion = [s for s in top if str(s.get("id", "")).startswith("occasion")]
    loyalty = [s for s in top if s.get("id") == _LOYALTY_SEGMENT_ID]
    thin = [s for s in top if float(s.get("share") or 0) < 0.03]

    parts = [
        "Wishlist hesitation is not one behavior — it splits by shopper type, not by phone or app version. "
        "We only name a segment when shoppers use explicit cues (sale wait, salary talk, wedding mention, etc.); "
        "shares below count comments with that cue, not every wishlist user."
    ]

    if price:
        parts.append(
            f"Price-first savers ({_join([str(s.get('label')) for s in price])} — "
            f"about {pct(_segment_group_share(price))} of these comments): "
            "the list works like a deal tracker. They plan to buy, but only after EORS, a price drop, "
            "or payday — the delay is timing or price, not loss of interest."
        )

    if loyalty:
        share = pct(loyalty[0].get("share"))
        parts.append(
            f"Loyal repeat shoppers ({share}): they already order on Myntra but still park items. "
            "Being a regular customer does not mean saved items convert quickly."
        )

    if trust:
        parts.append(
            f"Still-building-trust shoppers ({_join([str(s.get('label')) for s in trust])} — "
            f"about {pct(_segment_group_share(trust))}): "
            "new or cautious buyers save while they learn fit, quality, and whether products match photos. "
            "The wishlist is a shortlist for research, not a committed buy list."
        )

    if occasion:
        parts.append(
            f"Occasion-led shoppers ({_join([str(s.get('label')) for s in occasion])} — "
            f"about {pct(_segment_group_share(occasion))}): "
            "they save outfits for weddings, office, or festivals and pause until the look fits the moment — "
            "styling confidence gates the buy more than price."
        )

    if thin:
        parts.append(
            f"Gen Z, wedding, and festive cues are thinner in public wishlist talk "
            f"({_join([str(s.get('label')) for s in thin])}); "
            "treat those shares as directional and validate with survey quotas."
        )

    return " ".join(parts)


def _segments(ranked, job_w, blocker_w, intent, demographic_segments=None):
    del intent
    segments = [dict(s) for s in (demographic_segments or [])]
    # Occasion proxy from theme mix when explicit wedding/office text is thin
    occasion_share = float(job_w.get("occasion_social", 0.0) or 0.0) + float(
        blocker_w.get("styling_occasion", 0.0) or 0.0
    ) + float(blocker_w.get("social_validation", 0.0) or 0.0)
    if occasion_share >= 0.01 and not any(s.get("id", "").startswith("occasion_") for s in segments):
        segments.append(
            {
                "id": "occasion_based",
                "label": "Occasion-based shoppers",
                "diff": "They save for an occasion or social proof and wait until the look fits the moment.",
                "share": round(min(occasion_share, 1.0), 4),
                "n": None,
                "opportunity_ids": _ids_with_job(ranked, "occasion_social")
                or _ids_with_blocker(ranked, "styling_occasion"),
            }
        )
    deal_share = max(
        float(job_w.get("wait_for_sale", 0.0) or 0.0),
        float(blocker_w.get("sale_timing", 0.0) or 0.0),
    )
    if deal_share >= 0.01 and not any(s.get("id") == "deal_hunters" for s in segments):
        segments.append(
            {
                "id": "deal_hunters",
                "label": "Deal hunters / sale shoppers",
                "diff": "They save items and wait for EORS or a price drop — the list works like a personal sale alert.",
                "share": round(deal_share, 4),
                "n": None,
                "opportunity_ids": _ids_with_job(ranked, "wait_for_sale"),
            }
        )
    budget_share = max(
        float(job_w.get("bookmark_later", 0.0) or 0.0),
        float(blocker_w.get("price", 0.0) or 0.0),
    )
    if budget_share >= 0.015 and not any(s.get("id") == "budget_salary" for s in segments):
        segments.append(
            {
                "id": "budget_salary",
                "label": "Budget / salary-cycle shoppers",
                "diff": "They save until salary or budget allows — timing drives the delay, not lack of desire.",
                "share": round(budget_share, 4),
                "n": None,
                "opportunity_ids": _ids_with_job(ranked, "bookmark_later"),
            }
        )

    segments.sort(key=lambda s: (-float(s.get("share") or 0), str(s.get("label") or "")))
    if not segments:
        return (
            "Comments do not yet show clear shopper-type patterns (deal hunters, repeat buyers, occasion shoppers). "
            "We only name a segment when shoppers use explicit cues — we do not infer age from Android or iOS."
        ), [
            "Looking for: sale-wait language, repeat vs first-time talk, wedding / office / festive occasions, salary-cycle cues."
        ], []

    top = segments[:6]
    answer = _segment_answer_narrative(top)
    evidence = []
    for s in top:
        label = s.get("label")
        share = pct(s.get("share"))
        n = s.get("n")
        evidence.append(f"{label}: {share}" + (f" (n={n})" if n else ""))
    ids = list(dict.fromkeys([i for s in top for i in (s.get("opportunity_ids") or [])]))[:4]
    return answer, evidence, ids


def _loud(ranked, job_w, blocker_w, intent):
    del intent
    needs = _consistent_unmet_needs(ranked, job_w, blocker_w)
    if not needs:
        return (
            "We do not yet see clear unmet needs that repeat across wishlist conversations. "
            "With more comments, this answer would list the gaps shoppers still need filled after saving an item."
        ), [], [str(ranked[0].get("opportunity_id"))] if ranked else []

    top = needs[:4]
    answer = (
        "Across user conversations, the unmet needs that emerge most consistently are gaps shoppers still need "
        "filled after they save an item — not restating the delay reasons themselves. The strongest repeating needs are: "
        + _join([n["need"] for n in top])
        + ". These are what people are missing before a wishlisted product turns into a purchase."
    )
    evidence = [f"{n['need']}: {pct(n['share'])}" for n in top]
    top_need_set = {n["need"] for n in top}
    loud_weak = [
        o
        for o in ranked
        if o.get("volume_rank") is not None
        and o.get("rank_90d") is not None
        and int(o["volume_rank"]) + 2 < int(o["rank_90d"])
        and not (_row_unmet_needs(o) & top_need_set)
    ][:2]
    for o in loud_weak:
        evidence.append(
            f"Often mentioned, weaker as a wishlist unmet need: {_plain_problem(o)} "
            f"(mentioned #{o.get('volume_rank')}, conversion rank #{o.get('rank_90d')})"
        )
    ids = list(dict.fromkeys([i for n in top for i in n.get("opportunity_ids", [])]))[:4]
    if not ids:
        ids = [str(o.get("opportunity_id")) for o in ranked[:3]]
    return answer, evidence, ids


# Blocker / job → unmet need (what shoppers still lack)
_BLOCKER_UNMET_NEEDS = {
    "sale_timing": "clear alerts when a saved item’s price drops or a sale starts",
    "price": "a price they feel is fair enough to buy the saved item now",
    "fit": "confidence that the saved size will fit before they order",
    "size_chart": "a size chart they can trust for saved fashion items",
    "photo_mismatch": "proof the product looks like the photos or haul videos",
    "fabric_quality": "clarity on fabric and quality before they commit",
    "returns": "trust that returns will be easy if the saved item doesn’t work",
    "authenticity": "reassurance that the saved item is authentic",
    "review_volume_trust": "enough trustworthy reviews to feel safe buying from the wishlist",
    "competitor_check": "an easy way to compare the saved item with options elsewhere",
    "social_validation": "social or friend confirmation before buying a saved look",
    "styling_occasion": "help knowing whether the saved look works for their occasion",
    "delivery_checkout_saved": "a smooth buy-from-wishlist checkout and delivery path",
}

_JOB_UNMET_NEEDS = {
    "wait_for_sale": "timely sale / price-drop help so saved items don’t sit until a sale",
    "bookmark_later": "a useful nudge when “save for later” should become “buy now”",
    "impulse_park": "follow-up after impulse saves so items don’t go stale",
    "intent_blocked": "help clearing the blocker so real purchase intent can convert",
    "shortlist_compare": "a simple way to compare multiple shortlisted products",
    "occasion_social": "occasion or social proof tied to the saved item",
}


def _row_unmet_needs(row: Mapping[str, Any]) -> set[str]:
    out: set[str] = set()
    bmix = row.get("blocker_mix") if isinstance(row.get("blocker_mix"), dict) else {}
    jmix = row.get("job_mix") if isinstance(row.get("job_mix"), dict) else {}
    for key, share in bmix.items():
        if float(share or 0) <= 0:
            continue
        need = _BLOCKER_UNMET_NEEDS.get(key)
        if need:
            out.add(need)
    for key, share in jmix.items():
        if float(share or 0) <= 0:
            continue
        need = _JOB_UNMET_NEEDS.get(key)
        if need:
            out.add(need)
    return out


def _consistent_unmet_needs(
    ranked: list[Mapping[str, Any]],
    job_w: dict[str, float],
    blocker_w: dict[str, float],
) -> list[dict[str, Any]]:
    """Aggregate repeating unmet needs from blockers/jobs and top conversion themes."""
    scores: dict[str, float] = {}
    ids_by_need: dict[str, list[str]] = {}

    def _add(need: str, share: float, oid: str | None = None) -> None:
        if not need or share <= 0:
            return
        scores[need] = scores.get(need, 0.0) + float(share)
        if oid:
            ids_by_need.setdefault(need, [])
            if oid not in ids_by_need[need]:
                ids_by_need[need].append(oid)

    for key, share in blocker_w.items():
        if key == "unknown":
            continue
        _add(_BLOCKER_UNMET_NEEDS.get(key, ""), share)

    for key, share in job_w.items():
        if key == "unknown":
            continue
        _add(_JOB_UNMET_NEEDS.get(key, ""), share * 0.5)

    for row in ranked[:6]:
        oid = str(row.get("opportunity_id") or "")
        weight = max(float(row.get("prevalence_relevant") or 0), 0.02) * (
            1.0 + 0.15 * float(row.get("metric_relevance") or 0)
        )
        bmix = row.get("blocker_mix") if isinstance(row.get("blocker_mix"), dict) else {}
        jmix = row.get("job_mix") if isinstance(row.get("job_mix"), dict) else {}
        for key, share in bmix.items():
            need = _BLOCKER_UNMET_NEEDS.get(key)
            if need and float(share or 0) > 0:
                _add(need, weight * float(share), oid)
        for key, share in jmix.items():
            need = _JOB_UNMET_NEEDS.get(key)
            if need and float(share or 0) > 0:
                _add(need, weight * float(share) * 0.5, oid)

    if not scores:
        return []

    total = sum(scores.values()) or 1.0
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {
            "need": need,
            "share": round(score / total, 4),
            "opportunity_ids": ids_by_need.get(need, [])[:2],
        }
        for need, score in ordered
    ]


def _plain_problem(row: Mapping[str, Any]) -> str:
    text = str(row.get("problem_one_liner") or row.get("opportunity_id") or "this topic").strip()
    for prefix in ("Users ", "People ", "Shoppers "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            if text:
                text = text[0].lower() + text[1:]
            break
    return text.rstrip(".")


def _weighted_mix(rows: list[Mapping[str, Any]], field: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    weight_sum = 0.0
    for row in rows:
        w = float(row.get("member_n") or 0) or 1.0
        mix = row.get(field) if isinstance(row.get(field), dict) else {}
        weight_sum += w
        for key, share in mix.items():
            totals[key] = totals.get(key, 0.0) + w * float(share or 0)
    if weight_sum <= 0:
        return {}
    return {k: round(v / weight_sum, 4) for k, v in totals.items()}


def _weighted_intent(rows: list[Mapping[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    weight_sum = 0.0
    for row in rows:
        mix = row.get("intent_vs_bookmark")
        if not isinstance(mix, dict):
            continue
        w = float(row.get("member_n") or 0) or 1.0
        weight_sum += w
        for key, share in mix.items():
            totals[key] = totals.get(key, 0.0) + w * float(share or 0)
    if weight_sum <= 0:
        return {}
    return {k: round(v / weight_sum, 4) for k, v in totals.items()}


def _source_share(rows: list[Mapping[str, Any]]) -> dict[str, float]:
    return _weighted_mix(rows, "source_mix")


def _top_keys(mix: dict[str, float], n: int) -> list[str]:
    items = [(k, v) for k, v in mix.items() if k != "unknown" and v > 0]
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in items[:n]]


def _ids_with_job(rows: list[Mapping[str, Any]], job: str) -> list[str]:
    out = []
    for row in rows:
        mix = row.get("job_mix") if isinstance(row.get("job_mix"), dict) else {}
        if float(mix.get(job) or 0) > 0:
            out.append(str(row.get("opportunity_id")))
    return out[:4]


def _ids_with_blocker(rows: list[Mapping[str, Any]], blocker: str) -> list[str]:
    out = []
    for row in rows:
        mix = row.get("blocker_mix") if isinstance(row.get("blocker_mix"), dict) else {}
        if float(mix.get(blocker) or 0) > 0:
            out.append(str(row.get("opportunity_id")))
    return out[:4]


def _join(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def _fmt_share(mix: dict[str, float]) -> str:
    items = sorted(mix.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{k} {pct(v)}" for k, v in items[:6]) or "—"


def _scenario_label(scenario: str) -> str:
    return {
        "general": "Wishlist → purchase (in general)",
        "within_30d": "Within 30 days of saving",
        "both": "Both horizons",
    }.get(scenario, scenario)
