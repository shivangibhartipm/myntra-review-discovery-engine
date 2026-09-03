"""Source adapter registry."""

from __future__ import annotations

from review_engine.config import AppConfig, SourceConfig
from review_engine.sources.app_store import AppStoreAdapter
from review_engine.sources.base import SourceAdapter
from review_engine.sources.play import PlayAdapter
from review_engine.sources.reddit import RedditAdapter
from review_engine.sources.stub import StubAdapter
from review_engine.sources.youtube import YouTubeAdapter

_ADAPTERS: dict[str, type[SourceAdapter]] = {
    "stub": StubAdapter,
    "play": PlayAdapter,
    "app_store": AppStoreAdapter,
    "reddit": RedditAdapter,
    "youtube": YouTubeAdapter,
}

PHASE1_SOURCES = ("play", "app_store", "reddit", "youtube")


def register(name: str, adapter_cls: type[SourceAdapter]) -> None:
    _ADAPTERS[name] = adapter_cls


def build_adapter(name: str, source_config: SourceConfig) -> SourceAdapter:
    if name not in _ADAPTERS:
        raise KeyError(f"no adapter registered for source {name!r}")
    return _ADAPTERS[name](source_config)


def enabled_adapters(config: AppConfig) -> dict[str, SourceAdapter]:
    adapters: dict[str, SourceAdapter] = {}
    for name, spec in config.sources.items():
        if not spec.enabled:
            continue
        if name not in _ADAPTERS:
            continue
        adapters[name] = build_adapter(name, spec)
    return adapters
