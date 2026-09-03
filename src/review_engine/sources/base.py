from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterator

from review_engine.config import SourceConfig
from review_engine.records import CanonicalDocument
from review_engine.windows import Cutoffs


@dataclass(frozen=True)
class Page:
    items: list[dict[str, Any]]
    next_cursor: str | None = None
    exhausted: bool = True


class SourceAdapter(ABC):
    """Per-source collector contract (Phase 0 interface; real adapters in Phase 1)."""

    name: str

    newest_first: bool = True

    def __init__(self, config: SourceConfig) -> None:
        self.config = config

    def is_available(self) -> tuple[bool, str]:
        return True, "ok"

    @abstractmethod
    def respect_robots_or_tos(self, url: str | None) -> bool:
        """Fail closed for live sources: False if ToS/robots are unknown or forbid collection."""

    @abstractmethod
    def fetch_page(self, cursor: str | None) -> Page:
        """One page of raw records. Stop when observed_at is outside the window or quota is hit."""

    @abstractmethod
    def normalize(self, raw: dict[str, Any], *, collected_at, bounds: Cutoffs) -> CanonicalDocument:
        """Map a raw item to the canonical record; must run PII scrubbing."""

    def iter_pages(self, start_cursor: str | None = None) -> Iterator[Page]:
        cursor = start_cursor
        while True:
            page = self.fetch_page(cursor)
            yield page
            if page.exhausted or page.next_cursor is None:
                return
            cursor = page.next_cursor
