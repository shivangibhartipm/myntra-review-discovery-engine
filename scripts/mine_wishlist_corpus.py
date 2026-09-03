#!/usr/bin/env python3
"""Mine raw corpus for wishlist / save / frequency language and behavioral themes."""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from review_engine.wishlist_themes import THEME_BY_ID, detect_wishlist_themes  # noqa: E402

DB = ROOT / "data" / "engine.db"


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT text, source FROM raw_documents WHERE source != 'stub'").fetchall()
    print(f"Total documents: {len(rows)}")
    theme_counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = {}
    for row in rows:
        text = row["text"] or ""
        for theme_id in detect_wishlist_themes(text):
            theme_counts[theme_id] += 1
            bucket = samples.setdefault(theme_id, [])
            if len(bucket) < 2:
                bucket.append(text[:180].replace("\n", " ").encode("ascii", "replace").decode())
    print("\n--- Behavioral themes (why items stay saved) ---")
    for theme_id, count in theme_counts.most_common():
        label = THEME_BY_ID[theme_id].label
        print(f"{theme_id}: {count}  ({label})")
        for sample in samples.get(theme_id, []):
            print(f"  - {sample}")
    conn.close()


if __name__ == "__main__":
    main()
