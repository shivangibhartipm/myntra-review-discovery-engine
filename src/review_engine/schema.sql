-- Logical stores from docs/architecture.md. SQLite for the local MVP.

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    phase TEXT NOT NULL,
    sources TEXT,
    config_snapshot TEXT,
    models TEXT,
    counts_in INTEGER NOT NULL DEFAULT 0,
    counts_out INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_rate REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS raw_documents (
    doc_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_native_id TEXT,
    url TEXT,
    observed_at TEXT,
    collected_at TEXT NOT NULL,
    text TEXT NOT NULL,
    lang TEXT,
    rating REAL,
    thread_id TEXT,
    product_or_category TEXT,
    corpus_layer TEXT,
    run_id TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS document_enrichment (
    doc_id TEXT PRIMARY KEY,
    is_relevant INTEGER,
    relevance_score REAL,
    relevance_reasons TEXT,
    filter_version TEXT,
    claims TEXT,
    jobs TEXT,
    blockers TEXT,
    postponement_beyond_30d TEXT,
    outside_myntra_info_seeking INTEGER,
    segment_clues TEXT,
    confidence REAL,
    evidence_span TEXT,
    embedding TEXT,
    cluster_id TEXT,
    cluster_version TEXT,
    extract_version TEXT,
    updated_at TEXT,
    FOREIGN KEY (doc_id) REFERENCES raw_documents(doc_id)
);

CREATE TABLE IF NOT EXISTS opportunity_areas (
    opportunity_id TEXT PRIMARY KEY,
    run_id TEXT,
    cluster_version TEXT,
    problem_one_liner TEXT,
    member_doc_ids TEXT,
    representative_doc_ids TEXT,
    job_mix TEXT,
    blocker_mix TEXT,
    source_mix TEXT,
    single_source_warning INTEGER,
    quotes TEXT,
    naming_source TEXT,
    rank_score REAL,
    rank_score_90d REAL,
    rank_score_12m REAL,
    rank_90d INTEGER,
    rank_12m INTEGER,
    volume_rank INTEGER,
    prevalence_relevant REAL,
    prevalence_unfiltered REAL,
    recency_90d_share REAL,
    postponement_rate REAL,
    metric_relevance REAL,
    actionability REAL,
    multi_source_support REAL,
    intent_vs_bookmark TEXT,
    delay_mechanism TEXT,
    segment_slices TEXT,
    comparison_notes TEXT,
    rank_version TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS collector_checkpoints (
    source TEXT PRIMARY KEY,
    cursor TEXT,
    last_observed_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_documents_source_layer
    ON raw_documents(source, corpus_layer);
CREATE INDEX IF NOT EXISTS idx_raw_documents_observed
    ON raw_documents(observed_at);

