"""Language policy: keep en and hi/Hinglish; drop others unless detection fails open to unknown."""

from __future__ import annotations

import re

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
KEEP_LANGS = {"en", "hi", "hinglish", "unknown"}


def detect_lang(text: str, hinted: str | None = None) -> str:
    sample = (text or "").strip()
    if not sample:
        return "unknown"
    if DEVANAGARI_RE.search(sample):
        return "hi"

    detected = _langdetect(sample)
    if detected in {"en", "hi"}:
        return detected
    if detected in {"id", "so", "sw", "tl", "et"} and _looks_like_hinglish(sample):
        return "hinglish"
    if detected is None:
        hinted_norm = (hinted or "").lower()
        if hinted_norm in {"en", "hi"}:
            return hinted_norm
        return "en" if sample.isascii() else "unknown"
    return detected


def should_keep_lang(lang: str | None) -> bool:
    return (lang or "unknown") in KEEP_LANGS


def _langdetect(text: str) -> str | None:
    try:
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = 0
        return detect(text[:4000])
    except Exception:
        return None


def _looks_like_hinglish(text: str) -> bool:
    lower = text.lower()
    markers = (
        "myntra",
        "wishlist",
        "kurta",
        "saree",
        "eors",
        "hai",
        "nahi",
        "acha",
        "accha",
        "bhai",
        "yaar",
        "size",
    )
    return any(m in lower for m in markers)
