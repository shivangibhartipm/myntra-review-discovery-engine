"""Reset collector checkpoints and run collect → present for more wishlist insights."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from review_engine.config import load_config
from review_engine.db import connect, init_db
from review_engine.env import load_local_env


def reset_checkpoints(conn, sources: list[str]) -> None:
    for source in sources:
        conn.execute("DELETE FROM collector_checkpoints WHERE source = ?", (source,))
    conn.commit()


def run_phase(phase: str, *, sources: str = "") -> None:
    cmd = [sys.executable, "-m", "review_engine", "--phase", phase]
    if sources:
        cmd.extend(["--sources", sources])
    print(f"\n>>> {' '.join(cmd)}\n", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    load_local_env()
    parser = argparse.ArgumentParser(description="Collect more comments and refresh the dashboard.")
    parser.add_argument(
        "--reset",
        default="youtube",
        help="Comma-separated sources to reset before collect (default: youtube). Use 'none' to skip.",
    )
    parser.add_argument(
        "--collect-sources",
        default="play,youtube",
        help="Sources to collect (default: play,youtube).",
    )
    parser.add_argument("--collect-only", action="store_true", help="Stop after collect phase.")
    args = parser.parse_args()

    config = load_config(ROOT / "config.yaml")
    conn = connect(config.storage.path)
    init_db(conn)

    if args.reset.lower() != "none":
        sources = [s.strip() for s in args.reset.split(",") if s.strip()]
        if sources:
            reset_checkpoints(conn, sources)
            print(f"Reset collector checkpoints for: {', '.join(sources)}")
    conn.close()

    run_phase("collect", sources=args.collect_sources)
    if args.collect_only:
        return 0

    for phase in ("filter", "extract", "cluster", "rank", "present"):
        run_phase(phase)
    print("\nDone. Refresh the dashboard to see updated insights.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
