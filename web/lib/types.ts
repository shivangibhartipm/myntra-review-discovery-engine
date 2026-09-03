export type Quote = {
  doc_id: string;
  source: string;
  observed_at: string;
  quote: string;
};

export type SegmentSlice = {
  clue: string;
  n: number;
  postponement_rate: number;
};

export type StuckReasonCatalogEntry = {
  id: string;
  label: string;
  category: "blocker" | "conversion" | "ux" | "validation";
  count: number;
  share: number;
  is_blocker: boolean;
};

export type PlainCopy = {
  delay_strength: string;
  blocks_purchase_ever?: string;
  how_common: string;
  waiting_past_30d: string;
  jobs: string[];
  blockers: string[];
};

export type Opportunity = {
  opportunity_id: string;
  problem_one_liner: string;
  member_n: number;
  rank_90d: number | null;
  rank_12m: number | null;
  volume_rank: number | null;
  rank_score: number | null;
  rank_score_90d: number | null;
  rank_score_12m: number | null;
  metric_relevance: number | null;
  prevalence_relevant: number | null;
  prevalence_unfiltered: number | null;
  postponement_rate: number | null;
  recency_90d_share: number | null;
  actionability: number | null;
  delay_mechanism: string;
  comparison_notes: string;
  job_mix: Record<string, number>;
  blocker_mix: Record<string, number>;
  source_mix: Record<string, number>;
  jobs: string[];
  blockers: string[];
  sources: string[];
  corpus_layer_mix: Record<string, number>;
  categories: string[];
  segment_slices: SegmentSlice[];
  stuck_reason_mix?: Record<string, number>;
  stuck_reasons?: string[];
  suggested_lever: string;
  quotes: Quote[];
  single_source_warning: boolean;
  plain?: PlainCopy;
  intent_vs_bookmark?: Record<string, number>;
};

export type DemographicSegment = {
  id: string;
  label: string;
  diff: string;
  n: number;
  share: number;
  opportunity_ids: string[];
};

export type BriefQuestion = {
  id: string;
  question: string;
  scenario?: "general" | "within_30d" | "both";
  answer: string;
  evidence: string[];
  opportunity_ids: string[];
};

export type FirstBet = {
  opportunity_id: string;
  problem: string;
  why: string;
  lever: string;
  quote: string;
  delay_strength: string;
  blocks_purchase_ever?: string;
  how_common: string;
  waiting_past_30d: string;
};

export type BriefScenario = {
  id: "general" | "within_30d" | string;
  title: string;
  summary: string;
  evidence: string[];
  opportunity_ids: string[];
};

export type Briefing = {
  goal: string;
  first_bet: FirstBet | null;
  scenarios?: BriefScenario[];
  demographic_segments?: DemographicSegment[];
  questions: BriefQuestion[];
};

export type YieldRow = {
  unfiltered: number;
  scored: number;
  relevant: number;
  yield: number;
};

export type CorpusHealth = {
  n_unfiltered: number;
  n_relevant: number;
  yield_by_source: Record<string, YieldRow>;
  last_run: {
    run_id?: string;
    phase?: string;
    started_at?: string;
    finished_at?: string;
    counts_in?: number;
    counts_out?: number;
  };
  recent_runs: Record<string, unknown>[];
  windows: Record<string, string>;
  stuck_reason_catalog?: StuckReasonCatalogEntry[];
};

export type BoardPayload = {
  generated_at: string;
  present_version: string;
  headline: string;
  windows: Record<string, string>;
  corpus_health: CorpusHealth;
  message: string | null;
  briefing?: Briefing;
  opportunities: Opportunity[];
};
