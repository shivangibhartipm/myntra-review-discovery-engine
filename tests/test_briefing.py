from review_engine.present.briefing import QUESTIONS, build_briefing


def test_briefing_answers_problem_statement_questions():
    briefing = build_briefing(
        [
            {
                "opportunity_id": "wait_for_sale_sale_timing",
                "problem_one_liner": "Users wait for a sale before buying saved items.",
                "member_n": 4,
                "rank_90d": 1,
                "volume_rank": 3,
                "metric_relevance": 5,
                "prevalence_relevant": 0.1,
                "prevalence_unfiltered": 0.01,
                "postponement_rate": 1.0,
                "delay_mechanism": "Park until EORS.",
                "suggested_lever": "Wishlist price-drop alerts",
                "job_mix": {"wait_for_sale": 1.0},
                "blocker_mix": {"sale_timing": 1.0},
                "source_mix": {"play": 0.5, "reddit": 0.5},
                "intent_vs_bookmark": {"intent_blocked": 0.0, "bookmark_or_impulse": 0.2},
                "quotes": [{"quote": "waiting for EORS", "source": "reddit", "doc_id": "a", "observed_at": "2026-08-01"}],
                "segment_slices": [],
            },
            {
                "opportunity_id": "fit_uncertain",
                "problem_one_liner": "Fit is uncertain on saved items.",
                "member_n": 20,
                "rank_90d": 5,
                "volume_rank": 1,
                "metric_relevance": 4,
                "prevalence_relevant": 0.35,
                "prevalence_unfiltered": 0.2,
                "postponement_rate": 0.0,
                "delay_mechanism": "Won't checkout until size is clear.",
                "suggested_lever": "Fit confidence",
                "job_mix": {"intent_blocked": 1.0},
                "blocker_mix": {"fit": 1.0},
                "source_mix": {"play": 1.0},
                "intent_vs_bookmark": {"intent_blocked": 1.0, "bookmark_or_impulse": 0.0},
                "quotes": [],
                "segment_slices": [],
            },
            {
                "opportunity_id": "fabric_loud",
                "problem_one_liner": "Fabric quality complaints are common.",
                "member_n": 15,
                "rank_90d": 10,
                "volume_rank": 2,
                "metric_relevance": 2,
                "prevalence_relevant": 0.25,
                "prevalence_unfiltered": 0.4,
                "postponement_rate": 0.0,
                "delay_mechanism": "Loud quality talk.",
                "suggested_lever": "Inspect quotes",
                "job_mix": {"unknown": 1.0},
                "blocker_mix": {"fabric_quality": 1.0},
                "source_mix": {"play": 1.0},
                "quotes": [],
                "segment_slices": [],
            },
        ],
        demographic_segments=[
            {
                "id": "genz_youth",
                "label": "Gen Z / young shoppers",
                "diff": "College or Gen Z cues show up with wishlist hesitation.",
                "share": 0.04,
                "n": 8,
                "opportunity_ids": [],
            },
            {
                "id": "repeat_shoppers",
                "label": "Repeat / loyal shoppers",
                "diff": "They already shop on Myntra and still park items.",
                "share": 0.07,
                "n": 12,
                "opportunity_ids": [],
            },
            {
                "id": "occasion_wedding",
                "label": "Wedding / occasion shoppers",
                "diff": "They save looks for weddings and wait until the outfit feels right.",
                "share": 0.02,
                "n": 4,
                "opportunity_ids": [],
            },
        ],
    )
    assert briefing["first_bet"]["opportunity_id"] == "wait_for_sale_sale_timing"
    ids = [q["id"] for q in briefing["questions"]]
    assert ids == [qid for qid, _, _ in QUESTIONS]
    by_id = {q["id"]: q for q in briefing["questions"]}
    assert by_id["stops_purchase"]["scenario"] == "general"
    assert by_id["postpone_30d"]["scenario"] == "within_30d"
    assert by_id["why_wishlist"]["question"].startswith("Why do users add fashion products")
    assert "waiting for a sale" in by_id["why_wishlist"]["answer"]
    assert "fit" in by_id["stops_purchase"]["answer"]
    assert "uncertain" in by_id["stops_purchase"]["question"].lower()
    assert "uncertain" in by_id["stops_purchase"]["answer"].lower() or "doubt" in by_id["stops_purchase"]["answer"].lower()
    assert "uncertainties" not in by_id
    assert "EORS" in (briefing["first_bet"]["quote"] or "")
    assert "postpone" in by_id["postpone_30d"]["answer"].lower() or "month" in by_id["postpone_30d"]["answer"]
    assert "saving for later" in by_id["intent_vs_bookmark"]["answer"].lower() or "bookmark" in by_id["intent_vs_bookmark"]["answer"].lower()
    assert "unmet" in by_id["loud_vs_metric"]["question"].lower()
    assert "need" in by_id["loud_vs_metric"]["answer"].lower()
    assert "fit" in by_id["loud_vs_metric"]["answer"].lower() or "price" in by_id["loud_vs_metric"]["answer"].lower() or "sale" in by_id["loud_vs_metric"]["answer"].lower()
    # Should describe needs (gaps), not only restate opportunity problem lines
    assert "wait for a sale or price drop before buying saved items" not in by_id["loud_vs_metric"]["answer"]
    assert any("%" in line for line in by_id["loud_vs_metric"]["evidence"])
    assert "segment" in by_id["segments"]["question"].lower()
    assert "android" not in by_id["segments"]["answer"].lower()
    assert "ios" not in by_id["segments"]["answer"].lower()
    assert any(
        token in by_id["segments"]["answer"].lower()
        for token in ("gen z", "repeat", "occasion", "deal", "budget", "first-time", "shopper", "salary")
    )
    assert any("%" in line for line in by_id["segments"]["evidence"])
    assert not any(
        "platform:" in line.lower() or "category:myntra" in line.lower() for line in by_id["segments"]["evidence"]
    )
    scenario_ids = [s["id"] for s in briefing["scenarios"]]
    assert scenario_ids == ["general", "within_30d"]
    assert "in general" in briefing["scenarios"][0]["summary"].lower() or "wishlist" in briefing["scenarios"][0]["summary"].lower()
    assert "month" in briefing["scenarios"][1]["summary"].lower() or "30" in briefing["scenarios"][1]["summary"]


def test_empty_briefing():
    briefing = build_briefing([])
    assert briefing["first_bet"] is None
    assert all("enough comments" in q["answer"] for q in briefing["questions"])
    assert [s["id"] for s in briefing["scenarios"]] == ["general", "within_30d"]
