"""Reddit public OAuth API. Skips unless REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

from review_engine.dates import parse_datetime
from review_engine.http_client import request_json
from review_engine.pii import scrub_payload
from review_engine.rate_limit import RateLimiter
from review_engine.records import CanonicalDocument, build_canonical
from review_engine.sources.base import Page, SourceAdapter
from review_engine.windows import Cutoffs

JsonFn = Callable[..., Any]

_COMMENT_FETCH_RE = re.compile(
    r"wishlist|wish\s*list|saved for later|save for later|shortlist|bookmark|"
    r"cart vs|never buy|graveyard|price drop|wait(?:ing)? for sale|EORS|"
    r"size chart|myntra vs|compare|haul",
    re.I,
)


class RedditAdapter(SourceAdapter):
    name = "reddit"
    newest_first = True

    def __init__(self, config, fetch_json: JsonFn | None = None) -> None:
        super().__init__(config)
        self._fetch_json = fetch_json
        self._limiter = RateLimiter(config.rate_limit_rps)
        self._token: str | None = None

    def is_available(self) -> tuple[bool, str]:
        if os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"):
            return True, "ok"
        return False, "missing REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET"

    def respect_robots_or_tos(self, url: str | None) -> bool:
        if not url:
            return False
        host = urlparse(url).netloc.lower()
        return host.endswith("reddit.com")

    def _queries(self) -> list[str]:
        return [str(q) for q in (self.config.extra.get("queries") or ["myntra wishlist"])]

    def _comment_queries(self) -> list[str]:
        extra = self.config.extra.get("comment_queries")
        if extra:
            return [str(q) for q in extra]
        return self._queries()

    def _subreddits(self) -> list[str]:
        return [str(s).lstrip("r/") for s in (self.config.extra.get("subreddits") or [])]

    def _fetch_post_comments(self) -> bool:
        return bool(self.config.extra.get("fetch_post_comments", True))

    def fetch_page(self, cursor: str | None) -> Page:
        state = json.loads(cursor) if cursor else {"stage": "search", "index": 0, "after": None}
        self._limiter.wait()
        stage = state.get("stage", "search")
        index = int(state.get("index") or 0)
        after = state.get("after")

        if stage == "search":
            return self._search_stage("search", self._queries(), index, after, next_stage="comment_search")

        if stage == "comment_search":
            return self._search_stage(
                "comment_search",
                self._comment_queries(),
                index,
                after,
                next_stage="subreddit",
                search_type="comment",
            )

        if stage == "subreddit":
            subs = self._subreddits()
            if index >= len(subs):
                return Page(items=[], next_cursor=None, exhausted=True)
            query = str(self.config.extra.get("subreddit_query", "myntra"))
            data = self._get_json(
                f"https://oauth.reddit.com/r/{subs[index]}/search",
                params={
                    "q": query,
                    "sort": "new",
                    "t": "year",
                    "limit": 100,
                    "after": after,
                    "restrict_sr": True,
                    "raw_json": 1,
                },
            )
            items, next_after = _listing_items(data)
            items = self._maybe_expand_comments(items)
            if next_after:
                nxt = {"stage": "subreddit", "index": index, "after": next_after}
                return Page(items=items, next_cursor=json.dumps(nxt), exhausted=False)
            nxt = {"stage": "subreddit_comments", "index": index, "after": None}
            return Page(items=items, next_cursor=json.dumps(nxt), exhausted=False)

        if stage == "subreddit_comments":
            subs = self._subreddits()
            if index >= len(subs):
                return Page(items=[], next_cursor=None, exhausted=True)
            comment_q = str(self.config.extra.get("subreddit_comment_query", "myntra wishlist"))
            data = self._get_json(
                f"https://oauth.reddit.com/r/{subs[index]}/search",
                params={
                    "q": comment_q,
                    "sort": "new",
                    "t": "year",
                    "limit": 100,
                    "after": after,
                    "restrict_sr": True,
                    "type": "comment",
                    "raw_json": 1,
                },
            )
            items, next_after = _listing_items(data)
            if next_after:
                nxt = {"stage": "subreddit_comments", "index": index, "after": next_after}
                return Page(items=items, next_cursor=json.dumps(nxt), exhausted=False)
            nxt = {"stage": "subreddit_comments", "index": index + 1, "after": None}
            exhausted = index + 1 >= len(subs)
            return Page(items=items, next_cursor=None if exhausted else json.dumps(nxt), exhausted=exhausted)

        return Page(items=[], next_cursor=None, exhausted=True)

    def _search_stage(
        self,
        stage: str,
        queries: list[str],
        index: int,
        after: str | None,
        *,
        next_stage: str,
        search_type: str | None = None,
    ) -> Page:
        if index >= len(queries):
            if stage == "search" and self._subreddits():
                return self.fetch_page(json.dumps({"stage": next_stage, "index": 0, "after": None}))
            if stage == "comment_search" and self._subreddits():
                return self.fetch_page(json.dumps({"stage": "subreddit", "index": 0, "after": None}))
            return Page(items=[], next_cursor=None, exhausted=True)
        params: dict[str, Any] = {
            "q": queries[index],
            "sort": "new",
            "t": "year",
            "limit": 100,
            "after": after,
            "restrict_sr": False,
            "raw_json": 1,
        }
        if search_type:
            params["type"] = search_type
        data = self._get_json("https://oauth.reddit.com/search", params=params)
        items, next_after = _listing_items(data)
        if stage == "search":
            items = self._maybe_expand_comments(items)
        if next_after:
            nxt = {"stage": stage, "index": index, "after": next_after}
            return Page(items=items, next_cursor=json.dumps(nxt), exhausted=False)
        nxt = {"stage": next_stage, "index": index + 1, "after": None}
        if stage == "comment_search" and index + 1 >= len(queries) and not self._subreddits():
            return Page(items=items, next_cursor=None, exhausted=True)
        return Page(items=items, next_cursor=json.dumps(nxt), exhausted=False)

    def _maybe_expand_comments(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self._fetch_post_comments():
            return items
        out: list[dict[str, Any]] = []
        for item in items:
            out.append(item)
            payload = item.get("data") if isinstance(item.get("data"), dict) else item
            if not isinstance(payload, dict):
                continue
            title = str(payload.get("title") or "")
            body = str(payload.get("selftext") or "")
            if not _COMMENT_FETCH_RE.search(f"{title}\n{body}"):
                continue
            post_id = str(payload.get("id") or "")
            sub = str(payload.get("subreddit") or "")
            if not post_id or not sub:
                continue
            out.extend(self._pull_post_comments(post_id, sub))
        return out

    def _pull_post_comments(self, post_id: str, subreddit: str) -> list[dict[str, Any]]:
        self._limiter.wait()
        try:
            data = self._get_json(
                f"https://oauth.reddit.com/r/{subreddit}/comments/{post_id}.json",
                params={"limit": 100, "depth": 4, "sort": "top", "raw_json": 1},
            )
        except Exception:
            return []
        if not isinstance(data, list) or len(data) < 2:
            return []
        listing = (data[1].get("data") or {}) if isinstance(data[1], dict) else {}
        return _flatten_comments(listing.get("children") or [], post_id=post_id, subreddit=subreddit)

    def normalize(self, raw: dict[str, Any], *, collected_at: datetime, bounds: Cutoffs) -> CanonicalDocument:
        payload = scrub_payload(raw)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        post_id = str(data.get("id") or payload.get("post_id") or "")
        permalink = data.get("permalink") or ""
        url = f"https://www.reddit.com{permalink}" if permalink else "https://www.reddit.com/"
        title = str(data.get("title") or "").strip()
        body = str(data.get("selftext") or data.get("body") or "").strip()
        if title and body:
            text = f"{title}\n{body}".strip()
        else:
            text = title or body
        created = data.get("created_utc")
        observed = None
        if created is not None:
            observed = datetime.fromtimestamp(float(created), tz=timezone.utc).replace(tzinfo=None)
        else:
            observed = parse_datetime(data.get("created"))
        thread_id = str(data.get("link_id") or payload.get("post_id") or data.get("name") or post_id)
        sub = str(data.get("subreddit") or payload.get("subreddit") or "")
        return build_canonical(
            source=self.name,
            collected_at=collected_at,
            bounds=bounds,
            text=text,
            source_native_id=post_id or None,
            url=url,
            observed_at=observed,
            lang=None,
            thread_id=thread_id,
            product_or_category=sub or "reddit",
        )

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._fetch_json:
            return self._fetch_json(url, params=params) or {}
        token = self._access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": os.getenv("REDDIT_USER_AGENT", "myntra-review-discovery/0.1"),
        }
        return request_json("GET", url, headers=headers, params=params) or {}

    def _access_token(self) -> str:
        if self._token:
            return self._token
        client_id = os.getenv("REDDIT_CLIENT_ID", "")
        secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        data = request_json(
            "POST",
            "https://www.reddit.com/api/v1/access_token",
            headers={"User-Agent": os.getenv("REDDIT_USER_AGENT", "myntra-review-discovery/0.1")},
            auth=(client_id, secret),
            data={"grant_type": "client_credentials"},
        )
        self._token = str((data or {}).get("access_token") or "")
        if not self._token:
            raise RuntimeError("reddit token missing")
        return self._token


def _listing_items(data: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    listing = (data or {}).get("data") or {}
    children = listing.get("children") or []
    items = []
    for child in children:
        if not isinstance(child, dict):
            continue
        kind = child.get("kind")
        payload = child.get("data") or {}
        if kind in {"t3", "t1"} or payload.get("title") or payload.get("body"):
            row = dict(child)
            permalink = payload.get("permalink") or ""
            row["url"] = f"https://www.reddit.com{permalink}" if permalink else "https://www.reddit.com/"
            items.append(row)
    after = listing.get("after")
    return items, after


def _flatten_comments(
    children: list[Any],
    *,
    post_id: str,
    subreddit: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        kind = child.get("kind")
        payload = child.get("data") or {}
        if kind == "t1" and payload.get("body"):
            out.append(
                {
                    "kind": "t1",
                    "data": payload,
                    "post_id": post_id,
                    "subreddit": subreddit,
                    "url": f"https://www.reddit.com{payload.get('permalink') or ''}",
                }
            )
            replies = payload.get("replies")
            if isinstance(replies, dict):
                nested = ((replies.get("data") or {}).get("children") or [])
                out.extend(_flatten_comments(nested, post_id=post_id, subreddit=subreddit))
    return out
