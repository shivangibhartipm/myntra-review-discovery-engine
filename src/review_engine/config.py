from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"

CANONICAL_SOURCES = (
    "play",
    "app_store",
    "reddit",
    "youtube",
    "pdp",
    "quora",
    "mouthshut",
    "trustpilot",
    "competitor_store",
    "stub",
)


@dataclass(frozen=True)
class SourceConfig:
    name: str
    enabled: bool
    tier: str
    rate_limit_rps: float
    daily_quota: int
    extra: dict[str, Any]


@dataclass(frozen=True)
class ModelsConfig:
    runtime: str
    ollama_host: str
    generate: str
    generate_upgrade: str
    generate_small: str
    embed: str

    def as_dict(self) -> dict[str, str]:
        return {
            "runtime": self.runtime,
            "ollama_host": self.ollama_host,
            "generate": self.generate,
            "generate_upgrade": self.generate_upgrade,
            "generate_small": self.generate_small,
            "embed": self.embed,
        }


@dataclass(frozen=True)
class StorageConfig:
    backend: str
    path: Path


@dataclass(frozen=True)
class WindowsConfig:
    primary_months: int
    recency_days: int
    trend_start_months: int
    trend_end_months: int
    pdp_months: int


@dataclass(frozen=True)
class FilterConfig:
    version: str
    relevance_threshold: float
    borderline_threshold: float
    use_llm: bool
    skip_if_same_version: bool
    goldset_path: Path
    sample_path: Path


@dataclass(frozen=True)
class ExtractConfig:
    version: str
    use_llm: bool
    skip_if_same_version: bool
    goldset_path: Path
    export_path: Path


@dataclass(frozen=True)
class ClusterConfig:
    version: str
    min_opportunities: int
    max_opportunities: int
    min_cluster_size: int
    merge_cosine: float
    use_embed: bool
    use_llm: bool
    skip_if_same_version: bool
    export_path: Path
    name_overrides_path: Path


@dataclass(frozen=True)
class RankConfig:
    version: str
    min_segment_n: int
    top_n_compare: int
    export_path: Path
    w1_metric_relevance: float
    w2_postponement_rate: float
    w3_prevalence_relevant: float
    w4_recency_boost: float
    w5_actionability: float
    w6_loud_but_weak_penalty: float

    def weights_dict(self) -> dict[str, float]:
        return {
            "w1_metric_relevance": self.w1_metric_relevance,
            "w2_postponement_rate": self.w2_postponement_rate,
            "w3_prevalence_relevant": self.w3_prevalence_relevant,
            "w4_recency_boost": self.w4_recency_boost,
            "w5_actionability": self.w5_actionability,
            "w6_loud_but_weak_penalty": self.w6_loud_but_weak_penalty,
        }


@dataclass(frozen=True)
class PresentConfig:
    version: str
    export_path: Path
    quotes_dir: Path
    report_dir: Path
    web_data_dir: Path
    ranked_path: Path
    top_n_onepagers: int
    audit_path: Path


@dataclass(frozen=True)
class AppConfig:
    as_of: datetime | None
    storage: StorageConfig
    windows: WindowsConfig
    models: ModelsConfig
    filter: FilterConfig
    extract: ExtractConfig
    cluster: ClusterConfig
    rank: RankConfig
    present: PresentConfig
    sources: dict[str, SourceConfig]
    raw: dict[str, Any]


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    as_of_raw = raw.get("as_of")
    as_of = None
    if as_of_raw:
        as_of = datetime.fromisoformat(str(as_of_raw)).replace(tzinfo=None)

    storage_raw = raw.get("storage") or {}
    db_path = Path(storage_raw.get("path", "data/engine.db"))
    if not db_path.is_absolute():
        db_path = ROOT / db_path

    windows_raw = raw.get("windows") or {}
    models_raw = raw.get("models") or {}
    sources: dict[str, SourceConfig] = {}
    for name, spec in (raw.get("sources") or {}).items():
        spec = spec or {}
        sources[name] = SourceConfig(
            name=name,
            enabled=bool(spec.get("enabled", False)),
            tier=str(spec.get("tier", "")),
            rate_limit_rps=float(spec.get("rate_limit_rps", 0.5)),
            daily_quota=int(spec.get("daily_quota", 100)),
            extra={k: v for k, v in spec.items() if k not in {"enabled", "tier", "rate_limit_rps", "daily_quota"}},
        )

    rank_cfg = _load_rank_config(raw.get("rank") or {})
    return AppConfig(
        as_of=as_of,
        storage=StorageConfig(
            backend=str(storage_raw.get("backend", "sqlite")),
            path=db_path,
        ),
        windows=WindowsConfig(
            primary_months=int(windows_raw.get("primary_months", 12)),
            recency_days=int(windows_raw.get("recency_days", 90)),
            trend_start_months=int(windows_raw.get("trend_start_months", 24)),
            trend_end_months=int(windows_raw.get("trend_end_months", 18)),
            pdp_months=int(windows_raw.get("pdp_months", 12)),
        ),
        models=ModelsConfig(
            runtime=str(models_raw.get("runtime", "ollama")),
            ollama_host=str(models_raw.get("ollama_host", "http://127.0.0.1:11434")),
            generate=str(models_raw.get("generate", "qwen2.5:7b")),
            generate_upgrade=str(models_raw.get("generate_upgrade", "qwen2.5:14b")),
            generate_small=str(models_raw.get("generate_small", "llama3.2:3b")),
            embed=str(models_raw.get("embed", "nomic-embed-text")),
        ),
        filter=_load_filter_config(raw.get("filter") or {}),
        extract=_load_extract_config(raw.get("extract") or {}),
        cluster=_load_cluster_config(raw.get("cluster") or {}),
        rank=rank_cfg,
        present=_load_present_config(raw.get("present") or {}, rank_export=rank_cfg.export_path),
        sources=sources,
        raw=raw,
    )


def _load_filter_config(spec: dict[str, Any]) -> FilterConfig:
    gold = Path(spec.get("goldset_path", "eval/goldset/relevance.jsonl"))
    sample = Path(spec.get("sample_path", "data/filter_audit_sample.json"))
    if not gold.is_absolute():
        gold = ROOT / gold
    if not sample.is_absolute():
        sample = ROOT / sample
    return FilterConfig(
        version=str(spec.get("version", "filter_v1")),
        relevance_threshold=float(spec.get("relevance_threshold", 0.5)),
        borderline_threshold=float(spec.get("borderline_threshold", 0.35)),
        use_llm=bool(spec.get("use_llm", True)),
        skip_if_same_version=bool(spec.get("skip_if_same_version", True)),
        goldset_path=gold,
        sample_path=sample,
    )


def _load_extract_config(spec: dict[str, Any]) -> ExtractConfig:
    gold = Path(spec.get("goldset_path", "eval/goldset/jobs_blockers.jsonl"))
    export = Path(spec.get("export_path", "data/claims_export.jsonl"))
    if not gold.is_absolute():
        gold = ROOT / gold
    if not export.is_absolute():
        export = ROOT / export
    return ExtractConfig(
        version=str(spec.get("version", "extract_v1")),
        use_llm=bool(spec.get("use_llm", True)),
        skip_if_same_version=bool(spec.get("skip_if_same_version", True)),
        goldset_path=gold,
        export_path=export,
    )


def _load_cluster_config(spec: dict[str, Any]) -> ClusterConfig:
    export = Path(spec.get("export_path", "data/opportunities_unranked.json"))
    overrides = Path(spec.get("name_overrides_path", "data/opportunity_name_overrides.json"))
    if not export.is_absolute():
        export = ROOT / export
    if not overrides.is_absolute():
        overrides = ROOT / overrides
    return ClusterConfig(
        version=str(spec.get("version", "cluster_v1")),
        min_opportunities=int(spec.get("min_opportunities", 5)),
        max_opportunities=int(spec.get("max_opportunities", 12)),
        min_cluster_size=int(spec.get("min_cluster_size", 2)),
        merge_cosine=float(spec.get("merge_cosine", 0.88)),
        use_embed=bool(spec.get("use_embed", True)),
        use_llm=bool(spec.get("use_llm", True)),
        skip_if_same_version=bool(spec.get("skip_if_same_version", True)),
        export_path=export,
        name_overrides_path=overrides,
    )


def _load_rank_config(spec: dict[str, Any]) -> RankConfig:
    export = Path(spec.get("export_path", "data/opportunities_ranked.json"))
    if not export.is_absolute():
        export = ROOT / export
    return RankConfig(
        version=str(spec.get("version", "rank_v1")),
        min_segment_n=int(spec.get("min_segment_n", 30)),
        top_n_compare=int(spec.get("top_n_compare", 8)),
        export_path=export,
        w1_metric_relevance=float(spec.get("w1_metric_relevance", 1.0)),
        w2_postponement_rate=float(spec.get("w2_postponement_rate", 0.8)),
        w3_prevalence_relevant=float(spec.get("w3_prevalence_relevant", 0.5)),
        w4_recency_boost=float(spec.get("w4_recency_boost", 0.4)),
        w5_actionability=float(spec.get("w5_actionability", 0.6)),
        w6_loud_but_weak_penalty=float(spec.get("w6_loud_but_weak_penalty", 0.7)),
    )


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _load_present_config(spec: dict[str, Any], *, rank_export: Path) -> PresentConfig:
    ranked = spec.get("ranked_path")
    return PresentConfig(
        version=str(spec.get("version", "present_v1")),
        export_path=_resolve_path(str(spec.get("export_path", "data/opportunities.json"))),
        quotes_dir=_resolve_path(str(spec.get("quotes_dir", "data/quotes"))),
        report_dir=_resolve_path(str(spec.get("report_dir", "data/reports"))),
        web_data_dir=_resolve_path(str(spec.get("web_data_dir", "web/public/data"))),
        ranked_path=_resolve_path(str(ranked)) if ranked else rank_export,
        top_n_onepagers=int(spec.get("top_n_onepagers", 8)),
        audit_path=_resolve_path(str(spec.get("audit_path", "data/audit_snippets.jsonl"))),
    )


def add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.replace(year=year, month=month, day=day)


def subtract_months(dt: datetime, months: int) -> datetime:
    return add_months(dt, -months)
