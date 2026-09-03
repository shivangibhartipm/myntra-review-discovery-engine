"""YouTube Data API v3. Skips unless YOUTUBE_API_KEY is set. Caps videos, not the open web."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlparse

from review_engine.dates import parse_datetime
from review_engine.http_client import HttpError, request_json
from review_engine.pii import scrub_payload
from review_engine.rate_limit import RateLimiter
from review_engine.records import CanonicalDocument, build_canonical
from review_engine.sources.base import Page, SourceAdapter
from review_engine.windows import Cutoffs

JsonFn = Callable[..., Any]


class YouTubeAdapter(SourceAdapter):
    name = "youtube"
    newest_first = False

    def __init__(self, config, fetch_json: JsonFn | None = None) -> None:
        super().__init__(config)
        self._fetch_json = fetch_json
        self._limiter = RateLimiter(config.rate_limit_rps)
        self._video_ids: list[str] | None = None

    def is_available(self) -> tuple[bool, str]:
        if os.getenv("YOUTUBE_API_KEY"):
            return True, "ok"
        return False, "missing YOUTUBE_API_KEY"

    def respect_robots_or_tos(self, url: str | None) -> bool:
        if not url:
            return False
        host = urlparse(url).netloc.lower()
        return host.endswith("youtube.com") or host.endswith("googleapis.com")

    def _queries(self) -> list[str]:
        return [str(q) for q in (self.config.extra.get("search_queries") or ["Myntra haul"])]

    def _max_videos(self) -> int:
        return int(self.config.extra.get("max_videos", 40))

    def _search_orders(self) -> list[str]:
        orders = self.config.extra.get("search_orders")
        if orders:
            return [str(o) for o in orders]
        return ["relevance", "date"]

    def _max_results_per_query(self) -> int:
        return int(self.config.extra.get("max_results_per_query", 50))

    def fetch_page(self, cursor: str | None) -> Page:
        state = json.loads(cursor) if cursor else {"video_index": 0, "page_token": None}
        video_ids = self._ensure_videos()
        index = int(state.get("video_index") or 0)
        if index >= len(video_ids):
            return Page(items=[], next_cursor=None, exhausted=True)
        self._limiter.wait()
        video_id = video_ids[index]
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": int(self.config.extra.get("max_comments_per_video", 50)),
            "order": str(self.config.extra.get("comment_order", "relevance")),
            "textFormat": "plainText",
            "pageToken": state.get("page_token") or "",
            "key": os.getenv("YOUTUBE_API_KEY", ""),
        }
        if not params["pageToken"]:
            params.pop("pageToken")
        try:
            data = self._get_json("https://www.googleapis.com/youtube/v3/commentThreads", params=params)
        except HttpError as exc:
            if exc.status in {403, 404}:
                nxt = {"video_index": index + 1, "page_token": None}
                exhausted = index + 1 >= len(video_ids)
                return Page(items=[], next_cursor=None if exhausted else json.dumps(nxt), exhausted=exhausted)
            raise
        items = []
        for thread in data.get("items") or []:
            snippet = ((thread.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
            row = {
                "id": thread.get("id"),
                "video_id": video_id,
                "text": snippet.get("textDisplay") or snippet.get("textOriginal") or "",
                "publishedAt": snippet.get("publishedAt"),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
            items.append(row)
        next_page = data.get("nextPageToken")
        if next_page:
            nxt = {"video_index": index, "page_token": next_page}
            return Page(items=items, next_cursor=json.dumps(nxt), exhausted=False)
        nxt = {"video_index": index + 1, "page_token": None}
        exhausted = index + 1 >= len(video_ids)
        return Page(items=items, next_cursor=None if exhausted else json.dumps(nxt), exhausted=exhausted)

    def normalize(self, raw: dict[str, Any], *, collected_at: datetime, bounds: Cutoffs) -> CanonicalDocument:
        payload = scrub_payload(raw)
        video_id = str(payload.get("video_id") or "")
        text = str(payload.get("text") or "").strip()
        return build_canonical(
            source=self.name,
            collected_at=collected_at,
            bounds=bounds,
            text=text,
            source_native_id=str(payload.get("id") or "") or None,
            url=payload.get("url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None),
            observed_at=parse_datetime(payload.get("publishedAt")),
            lang=None,
            thread_id=video_id or None,
            product_or_category="myntra_haul",
        )

    def _ensure_videos(self) -> list[str]:
        if self._video_ids is not None:
            return self._video_ids
        ids: list[str] = []
        seen: set[str] = set()
        cap = self._max_videos()
        per_query = self._max_results_per_query()
        max_searches = int(self.config.extra.get("max_search_calls", 40))
        searches = 0
        for query in self._queries():
            if len(ids) >= cap or searches >= max_searches:
                break
            for order in self._search_orders():
                if len(ids) >= cap or searches >= max_searches:
                    break
                page_token: str | None = None
                while len(ids) < cap and searches < max_searches:
                    self._limiter.wait()
                    searches += 1
                    params: dict[str, Any] = {
                        "part": "snippet",
                        "type": "video",
                        "q": query,
                        "maxResults": min(50, per_query, cap - len(ids)),
                        "order": order,
                        "regionCode": str(self.config.extra.get("region", "IN")),
                        "key": os.getenv("YOUTUBE_API_KEY", ""),
                    }
                    if page_token:
                        params["pageToken"] = page_token
                    data = self._get_json(
                        "https://www.googleapis.com/youtube/v3/search",
                        params=params,
                    )
                    for item in data.get("items") or []:
                        vid = (
                            ((item.get("id") or {}).get("videoId"))
                            if isinstance(item.get("id"), dict)
                            else None
                        )
                        if vid and vid not in seen:
                            seen.add(vid)
                            ids.append(vid)
                        if len(ids) >= cap:
                            break
                    page_token = data.get("nextPageToken")
                    if not page_token or len(ids) >= cap:
                        break
        self._video_ids = ids
        return ids

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._fetch_json:
            return self._fetch_json(url, params=params) or {}
        return request_json("GET", url, params=params) or {}
