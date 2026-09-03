"""Apple App Store customer reviews via the public iTunes RSS feed."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlparse

from review_engine.dates import parse_datetime
from review_engine.http_client import request_json
from review_engine.pii import scrub_payload
from review_engine.rate_limit import RateLimiter
from review_engine.records import CanonicalDocument, build_canonical
from review_engine.sources.base import Page, SourceAdapter
from review_engine.windows import Cutoffs

JsonFn = Callable[[str], Any]


class AppStoreAdapter(SourceAdapter):
    name = "app_store"
    newest_first = True

    def __init__(self, config, fetch_json: JsonFn | None = None) -> None:
        super().__init__(config)
        self._fetch_json = fetch_json or (lambda url: request_json("GET", url))
        self._limiter = RateLimiter(config.rate_limit_rps)
        self.truncated = False

    def _app_id(self) -> str:
        return str(self.config.extra.get("app_id", "907394059"))

    def _country(self) -> str:
        return str(self.config.extra.get("country", "in"))

    def _max_pages(self) -> int:
        return int(self.config.extra.get("max_pages", 10))

    def rss_url(self, page: int) -> str:
        return (
            f"https://itunes.apple.com/{self._country()}/rss/customerreviews/"
            f"page={page}/id={self._app_id()}/sortby=mostrecent/json"
        )

    def respect_robots_or_tos(self, url: str | None) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        if "itunes.apple.com" in host and "/rss/customerreviews" in path:
            return True
        if host.endswith("apps.apple.com"):
            return True
        return False

    def fetch_page(self, cursor: str | None) -> Page:
        page_no = int(json.loads(cursor)["page"]) if cursor else 1
        if page_no > self._max_pages():
            self.truncated = True
            return Page(items=[], next_cursor=None, exhausted=True)
        self._limiter.wait()
        url = self.rss_url(page_no)
        payload = self._fetch_json(url) or {}
        entries = _entries(payload)
        items = []
        for entry in entries:
            if _label(entry, "im:rating") is None:
                continue
            row = dict(entry)
            row["url"] = url
            row["_listing_url"] = f"https://apps.apple.com/{self._country()}/app/id{self._app_id()}"
            items.append(row)
        if not items:
            return Page(items=[], next_cursor=None, exhausted=True)
        if page_no >= self._max_pages():
            self.truncated = True
            return Page(items=items, next_cursor=None, exhausted=True)
        return Page(items=items, next_cursor=json.dumps({"page": page_no + 1}), exhausted=False)

    def normalize(self, raw: dict[str, Any], *, collected_at: datetime, bounds: Cutoffs) -> CanonicalDocument:
        payload = scrub_payload(raw)
        rating = _label(payload, "im:rating")
        title = _label(payload, "title") or ""
        body = _label(payload, "content") or ""
        text = f"{title}\n{body}".strip()
        observed = parse_datetime(_label(payload, "updated") or _label(payload, "im:releaseDate"))
        native_id = _review_id(payload)
        listing = payload.get("_listing_url") or f"https://apps.apple.com/{self._country()}/app/id{self._app_id()}"
        return build_canonical(
            source=self.name,
            collected_at=collected_at,
            bounds=bounds,
            text=text,
            source_native_id=native_id,
            url=listing,
            observed_at=observed,
            lang="en",
            rating=float(rating) if rating is not None else None,
            product_or_category="myntra_app",
        )


def _label(node: Any, key: str) -> str | None:
    value = node.get(key) if isinstance(node, dict) else None
    if isinstance(value, dict):
        label = value.get("label")
        return str(label) if label is not None else None
    if value is None:
        return None
    return str(value)


def _review_id(entry: dict[str, Any]) -> str | None:
    raw_id = _label(entry, "id") or ""
    if "/id" in raw_id:
        return raw_id.rsplit("/id", 1)[-1].split("?")[0]
    return raw_id or None


def _entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    feed = payload.get("feed") or payload
    entry = feed.get("entry")
    if entry is None:
        return []
    if isinstance(entry, list):
        return [e for e in entry if isinstance(e, dict)]
    if isinstance(entry, dict):
        return [entry]
    return []
