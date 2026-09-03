from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from review_engine.collect import collect_from_adapter
from review_engine.config import AppConfig, StorageConfig, load_config
from review_engine.db import connect, counts_by_source_and_layer, init_db, start_run
from review_engine.rate_limit import RateLimiter
from review_engine.sources.app_store import AppStoreAdapter
from review_engine.sources.play import PlayAdapter
from review_engine.sources.reddit import RedditAdapter
from review_engine.sources.youtube import YouTubeAdapter
from review_engine.windows import cutoffs

AS_OF = datetime(2026, 8, 24, 12, 0, 0)

RSS_FEED = {
    "feed": {
        "entry": [
            {"im:name": {"label": "Myntra"}},
            {
                "id": {"label": "https://itunes.apple.com/in/review?id=907394059&type=1"},
                "title": {"label": "Waiting for sale"},
                "content": {"label": "Added kurtas to wishlist until EORS."},
                "im:rating": {"label": "4"},
                "updated": {"label": "2026-08-01T10:00:00-00:00"},
                "author": {"name": {"label": "Hidden User"}},
            },
            {
                "id": {"label": "https://itunes.apple.com/in/review?id=111&type=1"},
                "title": {"label": "Old review"},
                "content": {"label": "Five years ago this app was fine."},
                "im:rating": {"label": "5"},
                "updated": {"label": "2020-01-01T10:00:00-00:00"},
                "author": {"name": {"label": "Someone"}},
            },
        ]
    }
}


def _config(tmp_path: Path) -> AppConfig:
    base = load_config()
    sources = dict(base.sources)
    sources["play"] = replace(sources["play"], enabled=True, rate_limit_rps=100, daily_quota=50)
    sources["app_store"] = replace(sources["app_store"], enabled=True, rate_limit_rps=100, daily_quota=50)
    sources["reddit"] = replace(sources["reddit"], enabled=True)
    sources["youtube"] = replace(sources["youtube"], enabled=True)
    sources["stub"] = replace(sources["stub"], enabled=False)
    return replace(
        base,
        as_of=AS_OF,
        storage=StorageConfig(backend="sqlite", path=tmp_path / "engine.db"),
        sources=sources,
    )


def _conn(config: AppConfig, run_id: str = "p1"):
    conn = connect(config.storage.path)
    init_db(conn)
    bounds = cutoffs(config, AS_OF)
    start_run(
        conn,
        run_id=run_id,
        phase="collect",
        sources=["play"],
        config_snapshot={"windows": bounds.as_dict()},
        models=config.models.as_dict(),
    )
    return conn, bounds


def test_app_store_normalize_drops_author_and_uses_rss(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(RateLimiter, "wait", lambda self: None)
    config = _config(tmp_path)
    adapter = AppStoreAdapter(config.sources["app_store"], fetch_json=lambda url: RSS_FEED)
    assert adapter.respect_robots_or_tos(adapter.rss_url(1))
    assert not adapter.respect_robots_or_tos("https://evil.example/reviews")
    page = adapter.fetch_page(None)
    assert len(page.items) == 2
    conn, bounds = _conn(config)
    doc = adapter.normalize(page.items[0], collected_at=AS_OF, bounds=bounds)
    assert "wishlist" in doc.text.lower()
    assert "Hidden User" not in doc.text
    assert doc.source == "app_store"
    assert doc.rating == 4
    assert doc.corpus_layer == "recency_90d"
    conn.close()


def test_play_collect_stops_at_12_month_window(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(RateLimiter, "wait", lambda self: None)
    config = _config(tmp_path)

    def reviews_fn(app_id, lang="en", country="in", count=200, continuation_token=None):
        if lang != "en" or continuation_token:
            return [], None
        return [
            {
                "reviewId": "r-new",
                "userName": "Aisha K",
                "userImage": "https://example.invalid/a.png",
                "content": "Saved to wishlist until the sale. Waiting for EORS.",
                "score": 4,
                "at": datetime(2026, 8, 10, 8, 0, 0),
            },
            {
                "reviewId": "r-mid",
                "userName": "Rohit",
                "content": "Size chart is unclear so I have not bought the shortlisted pair.",
                "score": 3,
                "at": datetime(2026, 1, 15, 8, 0, 0),
            },
            {
                "reviewId": "r-old",
                "userName": "Old",
                "content": "Ancient review from before the window.",
                "score": 2,
                "at": datetime(2024, 1, 1, 8, 0, 0),
            },
        ], None

    adapter = PlayAdapter(config.sources["play"], reviews_fn=reviews_fn)
    conn, bounds = _conn(config)
    stats = collect_from_adapter(
        conn,
        adapter,
        config=config,
        run_id="p1",
        collected_at=AS_OF,
        bounds=bounds,
    )
    assert stats.counts_out == 2
    assert stats.skipped_window >= 1
    rows = conn.execute("SELECT source_native_id, corpus_layer, text FROM raw_documents ORDER BY observed_at DESC").fetchall()
    ids = [r["source_native_id"] for r in rows]
    assert ids == ["r-new", "r-mid"]
    assert rows[0]["corpus_layer"] == "recency_90d"
    assert rows[1]["corpus_layer"] == "primary_12m"
    assert "Aisha" not in rows[0]["text"]
    breakdown = counts_by_source_and_layer(conn)
    assert breakdown["by_source"]["play"] == 2
    assert breakdown["by_layer"]["recency_90d"] == 1
    conn.close()


def test_skips_non_en_hi_language(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(RateLimiter, "wait", lambda self: None)
    monkeypatch.setattr("review_engine.collect.detect_lang", lambda text, hinted=None: "fr")
    config = _config(tmp_path)

    def reviews_fn(app_id, lang="en", country="in", count=200, continuation_token=None):
        if lang != "en":
            return [], None
        return [
            {
                "reviewId": "r-fr",
                "content": "C'est terrible, l'application plante toujours pendant le paiement.",
                "score": 1,
                "at": datetime(2026, 8, 1, 8, 0, 0),
            }
        ], None

    adapter = PlayAdapter(config.sources["play"], reviews_fn=reviews_fn)
    conn, bounds = _conn(config)
    stats = collect_from_adapter(
        conn,
        adapter,
        config=config,
        run_id="p1",
        collected_at=AS_OF,
        bounds=bounds,
    )
    assert stats.counts_out == 0
    assert stats.skipped_lang == 1
    conn.close()


def test_reddit_and_youtube_skip_without_keys():
    config = load_config()
    reddit = RedditAdapter(config.sources["reddit"])
    youtube = YouTubeAdapter(config.sources["youtube"])
    ok_r, reason_r = reddit.is_available()
    ok_y, reason_y = youtube.is_available()
    assert ok_r is False
    assert "REDDIT_CLIENT_ID" in reason_r
    assert ok_y is False
    assert "YOUTUBE_API_KEY" in reason_y


def test_phase1_run_report(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(RateLimiter, "wait", lambda self: None)
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

    def reviews_fn(app_id, lang="en", country="in", count=200, continuation_token=None):
        if lang != "en":
            return [], None
        return [
            {
                "reviewId": "r1",
                "content": "I added this to my wishlist until salary day.",
                "score": 4,
                "at": datetime(2026, 8, 20, 8, 0, 0),
            }
        ], None

    monkeypatch.setattr("review_engine.sources.play._default_reviews", reviews_fn)
    monkeypatch.setattr(
        "review_engine.sources.app_store.request_json",
        lambda *args, **kwargs: RSS_FEED,
    )

    config = _config(tmp_path)
    conn, bounds = _conn(config, run_id="phase1")
    from phases.p1_collect.run import run

    counts_in, counts_out, errors, notes = run(
        conn,
        config=config,
        run_id="phase1",
        collected_at=AS_OF,
        bounds=bounds,
        source_filter=["play", "app_store", "reddit", "youtube"],
    )
    report = json.loads(notes)
    assert counts_out >= 2
    assert errors == 0
    assert "play" in report["per_source"]
    assert "app_store" in report["per_source"]
    assert any("reddit" in s for s in report["skipped"])
    assert any("youtube" in s for s in report["skipped"])
    assert report["by_source"]["play"] >= 1
    assert "recency_90d" in report["by_layer"]
    conn.close()
