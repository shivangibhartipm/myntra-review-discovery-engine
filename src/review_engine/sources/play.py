"""Google Play reviews via google-play-scraper (community client named in architecture P0)."""

from __future__ import annotations

import base64
import json
import pickle
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlparse

from review_engine.dates import parse_datetime
from review_engine.pii import scrub_payload
from review_engine.rate_limit import RateLimiter
from review_engine.records import CanonicalDocument, build_canonical
from review_engine.sources.base import Page, SourceAdapter
from review_engine.windows import Cutoffs

ReviewsFn = Callable[..., tuple[list[dict[str, Any]], Any]]


def _default_reviews(app_id: str, lang: str, country: str, count: int, continuation_token: Any):
    from google_play_scraper import Sort, reviews

    return reviews(
        app_id,
        lang=lang,
        country=country,
        sort=Sort.NEWEST,
        count=count,
        continuation_token=continuation_token,
    )


class PlayAdapter(SourceAdapter):
    name = "play"
    newest_first = True

    def __init__(self, config, reviews_fn: ReviewsFn | None = None) -> None:
        super().__init__(config)
        self._reviews_fn = reviews_fn or _default_reviews
        self._limiter = RateLimiter(config.rate_limit_rps)

    def _app_id(self) -> str:
        return str(self.config.extra.get("app_id", "com.myntra.android"))

    def _langs(self) -> list[str]:
        langs = self.config.extra.get("langs") or ["en", "hi"]
        return [str(x) for x in langs]

    def respect_robots_or_tos(self, url: str | None) -> bool:
        # Architecture P0: public listing via community scraper, not an ad-hoc site crawl.
        if not url:
            return True
        host = urlparse(url).netloc.lower()
        return host.endswith("play.google.com")

    def fetch_page(self, cursor: str | None) -> Page:
        self._limiter.wait()
        lang_index, token = _decode_cursor(cursor)
        langs = self._langs()
        if lang_index >= len(langs):
            return Page(items=[], next_cursor=None, exhausted=True)
        lang = langs[lang_index]
        country = str(self.config.extra.get("country", "in"))
        count = int(self.config.extra.get("page_size", 200))
        items, next_token = self._reviews_fn(
            self._app_id(),
            lang=lang,
            country=country,
            count=count,
            continuation_token=token,
        )
        tagged = []
        for item in items or []:
            row = dict(item)
            row["_play_lang"] = lang
            tagged.append(row)
        if next_token is None:
            if lang_index + 1 < len(langs):
                return Page(items=tagged, next_cursor=_encode_cursor(lang_index + 1, None), exhausted=False)
            return Page(items=tagged, next_cursor=None, exhausted=True)
        return Page(items=tagged, next_cursor=_encode_cursor(lang_index, next_token), exhausted=False)

    def normalize(self, raw: dict[str, Any], *, collected_at: datetime, bounds: Cutoffs) -> CanonicalDocument:
        payload = scrub_payload(raw)
        app_id = self._app_id()
        review_id = str(payload.get("reviewId") or payload.get("review_id") or "")
        observed = parse_datetime(payload.get("at") or payload.get("observed_at"))
        title = str(payload.get("title") or "").strip()
        body = str(payload.get("content") or payload.get("text") or "").strip()
        text = f"{title}\n{body}".strip() if title and title not in body else body
        url = f"https://play.google.com/store/apps/details?id={app_id}"
        if review_id:
            url = f"{url}&reviewId={review_id}"
        rating = payload.get("score")
        return build_canonical(
            source=self.name,
            collected_at=collected_at,
            bounds=bounds,
            text=text,
            source_native_id=review_id or None,
            url=url,
            observed_at=observed,
            lang=payload.get("_play_lang"),
            rating=float(rating) if rating is not None else None,
            product_or_category="myntra_app",
        )


def _encode_cursor(lang_index: int, token: Any) -> str:
    blob = None
    if token is not None:
        blob = base64.b64encode(pickle.dumps(token)).decode("ascii")
    return json.dumps({"lang_index": lang_index, "token": blob})


def _decode_cursor(cursor: str | None) -> tuple[int, Any]:
    if not cursor:
        return 0, None
    data = json.loads(cursor)
    token = data.get("token")
    if token:
        token = pickle.loads(base64.b64decode(token))
    return int(data.get("lang_index", 0)), token
