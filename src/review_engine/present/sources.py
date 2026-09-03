"""Sources excluded from dashboard artifacts (synthetic / dev-only data)."""

from __future__ import annotations

EXCLUDED_BOARD_SOURCES = frozenset({"stub"})


def is_board_source(source: str | None) -> bool:
    return bool(source) and source not in EXCLUDED_BOARD_SOURCES
