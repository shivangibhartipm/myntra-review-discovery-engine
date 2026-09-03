from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from review_engine.config import ROOT, load_config
from review_engine.db import connect, finish_run, init_db, start_run
from review_engine.env import load_local_env
from review_engine.windows import cutoffs, now_utc

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE_ALIASES = {
    "0": "foundations",
    "foundations": "foundations",
    "1": "collect",
    "collect": "collect",
    "2": "filter",
    "filter": "filter",
    "3": "extract",
    "extract": "extract",
    "4": "cluster",
    "cluster": "cluster",
    "5": "rank",
    "rank": "rank",
    "6": "present",
    "present": "present",
}


def _dispatch(phase: str):
    if phase == "foundations":
        from phases.p0_foundations.run import run as fn
    elif phase == "collect":
        from phases.p1_collect.run import run as fn
    elif phase == "filter":
        from phases.p2_filter.run import run as fn
    elif phase == "extract":
        from phases.p3_extract.run import run as fn
    elif phase == "cluster":
        from phases.p4_cluster.run import run as fn
    elif phase == "rank":
        from phases.p5_rank.run import run as fn
    elif phase == "present":
        from phases.p6_present.run import run as fn
    else:
        raise SystemExit(f"unknown phase {phase!r}")
    return fn


def main(argv: list[str] | None = None) -> int:
    load_local_env()
    parser = argparse.ArgumentParser(description="Myntra review discovery engine")
    parser.add_argument(
        "--phase",
        required=True,
        help="foundations|collect|filter|extract|cluster|rank|present (or 0–6)",
    )
    parser.add_argument("--sources", default="", help="comma-separated source names; empty = enabled in config")
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    args = parser.parse_args(argv)

    phase = PHASE_ALIASES.get(args.phase)
    if not phase:
        print(f"unknown phase {args.phase!r}", file=sys.stderr)
        return 2

    config = load_config(args.config)
    if config.storage.backend != "sqlite":
        print("only sqlite storage is supported", file=sys.stderr)
        return 2

    source_filter = [s.strip() for s in args.sources.split(",") if s.strip()]
    run_id = str(uuid.uuid4())
    collected_at = now_utc()
    bounds = cutoffs(config, collected_at)

    conn = connect(config.storage.path)
    init_db(conn)
    start_run(
        conn,
        run_id=run_id,
        phase=phase,
        sources=source_filter or [n for n, s in config.sources.items() if s.enabled],
        config_snapshot={
            "windows": bounds.as_dict(),
            "models": config.models.as_dict(),
            "storage": config.storage.backend,
        },
        models=config.models.as_dict(),
    )

    try:
        fn = _dispatch(phase)
        counts_in, counts_out, errors, notes = fn(
            conn,
            config=config,
            run_id=run_id,
            collected_at=collected_at,
            bounds=bounds,
            source_filter=source_filter,
        )
    except NotImplementedError as exc:
        finish_run(conn, run_id=run_id, counts_in=0, counts_out=0, error_count=1, notes=str(exc))
        conn.close()
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        finish_run(conn, run_id=run_id, counts_in=0, counts_out=0, error_count=1, notes=repr(exc))
        conn.close()
        raise

    finish_run(
        conn,
        run_id=run_id,
        counts_in=counts_in,
        counts_out=counts_out,
        error_count=errors,
        notes=notes,
    )
    conn.close()

    print(
        json.dumps(
            {
                "run_id": run_id,
                "phase": phase,
                "counts_in": counts_in,
                "counts_out": counts_out,
                "error_count": errors,
                "windows": bounds.as_dict(),
                "models": config.models.as_dict(),
                "db": str(config.storage.path),
                **_report_fields(notes),
            },
            indent=2,
        )
    )
    return 0


def _report_fields(notes: str | None) -> dict:
    if not notes:
        return {}
    try:
        parsed = json.loads(notes)
    except json.JSONDecodeError:
        return {"notes": notes}
    if isinstance(parsed, dict):
        return {"report": parsed}
    return {"notes": notes}


if __name__ == "__main__":
    raise SystemExit(main())
