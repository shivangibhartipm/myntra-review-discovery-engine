"""Analyze Myntra Wishlist Survey responses from Google Forms export."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

DEFAULT_PATH = Path(r"c:\Users\Shivangi Bharti\Downloads\Myntra Wishlist Survey  (Responses).xlsx")


def pct(x: int, base: int) -> float:
    return round(100 * x / base, 1) if base else 0.0


def value_counts_pct(series: pd.Series) -> list[tuple[str, int, float]]:
    valid = series.dropna()
    base = len(valid) or 1
    rows = []
    for val, cnt in valid.value_counts().items():
        rows.append((str(val), int(cnt), pct(int(cnt), base)))
    return rows


def split_multi(val) -> list[str]:
    if pd.isna(val):
        return []
    return [p.strip() for p in str(val).split(",") if p.strip()]


def target_segment(row: pd.Series) -> str:
    age = str(row["How old are you?"])
    orders = str(row["How many times have you ordered from Myntra in the last 12 months?"])
    adds = row["In the last 6 months, how many items have you added to your Myntra wishlist?"]
    unp = str(
        row[
            "Right now, do you have at least one item on your wishlist that you liked but haven't bought yet?"
        ]
    )
    age_ok = age in ("18–24", "25–35", "18-24", "25-35")
    repeat = orders in ("2 times", "3 or more times")
    adds_ok = str(adds) in ("2–5 items", "6 or more items", "2-5 items", "6 or more items")
    unp_ok = unp == "Yes"
    if age_ok and repeat and adds_ok and unp_ok:
        return "Primary target"
    if str(adds) == "None" or pd.isna(adds):
        return "Screened out (no wishlist adds)"
    if orders in ("0 times", "1 time"):
        return "Supplementary: light buyer"
    return "Other / partial fit"


BLOCKER_MAP = {
    "price": ["price", "expensive", "cost", "budget", "afford", "discount"],
    "sale_timing": ["sale", "eors", "offer", "deal", "wait", "drop"],
    "fit": ["size", "fit", "fitting"],
    "trust": ["trust", "quality", "fake", "review", "photo", "image", "authentic"],
    "compare": ["compar", "option", "another", "flipkart", "amazon", "ajio"],
    "occasion": ["occasion", "wedding", "festive", "office", "party", "event"],
    "forget": ["forget", "remember", "remind", "notification", "alert"],
}


def tag_text(text: str) -> list[str]:
    t = str(text).lower()
    tags = [k for k, words in BLOCKER_MAP.items() if any(w in t for w in words)]
    return tags or ["other"]


def analyze(path: Path) -> dict:
    df = pd.read_excel(path)
    n = len(df)
    why_col = "Why do you usually save items to your wishlist?"

    why_counts: Counter[str] = Counter()
    for val in df[why_col]:
        for opt in split_multi(val):
            why_counts[opt] += 1

    df["segment_fit"] = df.apply(target_segment, axis=1)

    oe1 = df[
        "Think of one wishlisted item you did not buy within a month. What stopped you?"
    ].dropna()
    oe2 = df[
        "What is one thing Myntra could do to help you buy more from your wishlist?"
    ].dropna()

    oe_tags: Counter[str] = Counter()
    for t in oe1:
        for tag in tag_text(t):
            oe_tags[tag] += 1

    help_tags: Counter[str] = Counter()
    for t in oe2:
        for tag in tag_text(t):
            help_tags[tag] += 1

    remember_col = (
        "Without opening the app right now, do you know you have items on your Myntra wishlist?"
    )
    freq_col = "How often do you open or check your Myntra wishlist?"
    thought_col = "Before this survey, had you thought about that item since you saved it?"

    forgot = int(df[remember_col].str.contains("forgot", case=False, na=False).sum())
    unsure = int(df[remember_col].str.contains("not sure", case=False, na=False).sum())
    know = int(df[remember_col].str.contains("roughly know", case=False, na=False).sum())
    rarely = int(df[freq_col].str.contains("Rarely|almost never", case=False, na=False).sum())
    not_thought = int(df[thought_col].str.contains("No|not thought|forgot", case=False, na=False).sum())

    why_themes = {
        "sale_or_price_drop": int(
            sum(1 for v in df[why_col] if "sale" in str(v).lower() or "price drop" in str(v).lower())
        ),
        "budget_salary": int(
            sum(1 for v in df[why_col] if "budget" in str(v).lower() or "salary" in str(v).lower())
        ),
        "comparing": int(sum(1 for v in df[why_col] if "comparing" in str(v).lower())),
        "fit_size": int(
            sum(1 for v in df[why_col] if "size" in str(v).lower() or "fit" in str(v).lower())
        ),
        "occasion": int(sum(1 for v in df[why_col] if "occasion" in str(v).lower())),
        "remember_later": int(sum(1 for v in df[why_col] if "remember" in str(v).lower())),
        "reviews_photos": int(
            sum(1 for v in df[why_col] if "review" in str(v).lower() or "photo" in str(v).lower())
        ),
    }

    return {
        "n": n,
        "age": value_counts_pct(df["How old are you?"]),
        "orders_12m": value_counts_pct(
            df["How many times have you ordered from Myntra in the last 12 months?"]
        ),
        "myntra_use": value_counts_pct(df["How do you mostly use Myntra?"]),
        "shop_style": value_counts_pct(df["How do you usually shop on Myntra?"]),
        "unpurchased": value_counts_pct(
            df[
                "Right now, do you have at least one item on your wishlist that you liked but haven't bought yet?"
            ]
        ),
        "adds_6m": value_counts_pct(
            df["In the last 6 months, how many items have you added to your Myntra wishlist?"].dropna()
        ),
        "segment_fit": value_counts_pct(df["segment_fit"]),
        "why_save": [(k, why_counts[k], pct(why_counts[k], n)) for k, _ in why_counts.most_common()],
        "why_save_themes": {k: (v, pct(v, n)) for k, v in why_themes.items()},
        "wishlist_size": value_counts_pct(df["Roughly how many items are on your wishlist right now?"]),
        "remember": value_counts_pct(df[remember_col]),
        "check_freq": value_counts_pct(df[freq_col]),
        "thought_about": value_counts_pct(df[thought_col]),
        "main_blocker": value_counts_pct(
            df["What is usually the main reason you don't buy something on your wishlist?"]
        ),
        "while_sitting": value_counts_pct(
            df["While an item is sitting on your wishlist, what do you usually do?"]
        ),
        "outside": value_counts_pct(
            df["Have you ever checked outside Myntra before buying something from your wishlist?"]
        ),
        "remember_summary": {
            "know_roughly": (know, pct(know, n)),
            "unsure": (unsure, pct(unsure, n)),
            "forgot": (forgot, pct(forgot, n)),
        },
        "rarely_check": (rarely, pct(rarely, n)),
        "not_thought_since_save": (not_thought, pct(not_thought, n)),
        "open_stopped_n": len(oe1),
        "open_help_n": len(oe2),
        "open_stopped_tags": oe_tags.most_common(),
        "open_help_tags": help_tags.most_common(),
        "open_stopped": oe1.tolist(),
        "open_help": oe2.tolist(),
        "remember_x_freq": pd.crosstab(df[remember_col], df[freq_col]).to_dict(),
    }


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    out = analyze(path)
    summary = {k: v for k, v in out.items() if k not in ("open_stopped", "open_help")}
    print(json.dumps(summary, indent=2, default=str))
    print("\n--- OPEN STOPPED ---")
    for i, t in enumerate(out["open_stopped"], 1):
        print(f"{i}. {t}")
    print("\n--- OPEN HELP ---")
    for i, t in enumerate(out["open_help"], 1):
        print(f"{i}. {t}")


if __name__ == "__main__":
    main()
