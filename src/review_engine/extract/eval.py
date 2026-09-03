from __future__ import annotations

from typing import Any

from review_engine.config import AppConfig
from review_engine.eval_gold import load_gold
from review_engine.extract.pipeline import extract_claim


def evaluate_extract_gold(config: AppConfig, llm_fn=None) -> dict[str, Any]:
    rows = load_gold(config.extract.goldset_path)
    if not rows:
        return {"n": 0, "job_f1": None, "blocker_f1": None, "span_valid": None, "skipped": "empty gold set"}
    job_tp = job_fp = job_fn = 0
    blk_tp = blk_fp = blk_fn = 0
    span_ok = 0
    postpone_ok = 0
    for i, row in enumerate(rows):
        text = str(row["text"])
        pred = extract_claim(doc_id=f"gold-{i}", text=text, config=config, llm_fn=llm_fn)
        gold_jobs = set(row.get("jobs") or [])
        gold_blk = set(row.get("blockers") or [])
        pred_jobs = set(pred.jobs)
        pred_blk = set(pred.blockers)
        job_tp += len(pred_jobs & gold_jobs)
        job_fp += len(pred_jobs - gold_jobs)
        job_fn += len(gold_jobs - pred_jobs)
        blk_tp += len(pred_blk & gold_blk)
        blk_fp += len(pred_blk - gold_blk)
        blk_fn += len(gold_blk - pred_blk)
        if pred.evidence_span and pred.evidence_span in text:
            span_ok += 1
        gold_p = str(row.get("postponement_beyond_30d") or "unknown")
        if pred.postponement_beyond_30d == gold_p:
            postpone_ok += 1
    return {
        "n": len(rows),
        "job_f1": _f1(job_tp, job_fp, job_fn),
        "blocker_f1": _f1(blk_tp, blk_fp, blk_fn),
        "span_valid": round(span_ok / len(rows), 4),
        "postpone_accuracy": round(postpone_ok / len(rows), 4),
    }


def _f1(tp: int, fp: int, fn: int) -> float:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)
