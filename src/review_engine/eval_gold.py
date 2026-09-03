from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from review_engine.config import AppConfig
from review_engine.relevance.pipeline import classify_text


def load_gold(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def evaluate_gold(config: AppConfig, judge=None) -> dict[str, Any]:
    rows = load_gold(config.filter.goldset_path)
    if not rows:
        return {"n": 0, "precision": None, "recall": None, "skipped": "empty gold set"}

    tp = fp = tn = fn = 0
    for row in rows:
        pred = classify_text(str(row["text"]), config, judge=judge)
        gold = bool(row["is_relevant"])
        if pred.is_relevant and gold:
            tp += 1
        elif pred.is_relevant and not gold:
            fp += 1
        elif not pred.is_relevant and not gold:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "n": len(rows),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
    }
