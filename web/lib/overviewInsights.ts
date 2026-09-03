import type { Briefing, BriefScenario, CorpusHealth, DemographicSegment, Opportunity } from "@/lib/types";
import { easyCopy, shortProblem } from "@/lib/plainLanguage";
import {
  hypothesisToTest,
  reasonOptionLabel,
  uniqueTopics,
} from "@/lib/compareInsights";

export type OverviewReason = {
  id: string;
  label: string;
  mentionPct: number | null;
  waitsPastMonth: boolean;
  rank: number;
};

export type ScenarioCard = {
  id: string;
  question: string;
  answer: string;
  reasons: { id: string; label: string; detail?: string }[];
};

function mentionPct(row: Opportunity): number | null {
  if (row.prevalence_relevant != null) return Math.round(row.prevalence_relevant * 100);
  const match = row.plain?.how_common?.match(/([\d.]+)%/);
  return match ? Math.round(Number(match[1])) : null;
}

function waitsPastMonth(row: Opportunity): boolean {
  if (row.postponement_rate != null) return row.postponement_rate >= 0.5;
  const text = row.plain?.waiting_past_30d?.toLowerCase() ?? "";
  return text.includes("most comments") || text.includes("often");
}

export function topStuckReasonTags(corpus?: CorpusHealth, limit = 6): { label: string; sharePct: number }[] {
  const catalog = corpus?.stuck_reason_catalog ?? [];
  return catalog
    .filter((row) => row.is_blocker && row.count > 0)
    .slice(0, limit)
    .map((row) => ({
      label: row.label,
      sharePct: Math.round(row.share * 100),
    }));
}

export function topReasons(opportunities: Opportunity[], limit = 3): OverviewReason[] {
  return uniqueTopics(opportunities)
    .slice(0, limit)
    .map((row, index) => ({
      id: row.opportunity_id,
      label: reasonOptionLabel(row),
      mentionPct: mentionPct(row),
      waitsPastMonth: waitsPastMonth(row),
      rank: index + 1,
    }));
}

export function buildHeadline(
  opportunities: Opportunity[],
  corpus?: CorpusHealth,
): { lead: string; support: string } {
  const topics = uniqueTopics(opportunities);
  const top = topics[0];
  const n = corpus?.n_relevant ?? opportunities.reduce((sum, row) => sum + row.member_n, 0);
  const label = top ? reasonOptionLabel(top) : "several reasons";

  const lead = top
    ? `“${label}” is the strongest reason people delay buying saved items.`
    : "Shopper comments point to several reasons people delay buying saved items.";

  const support = `From ${n.toLocaleString()} comments about saved items, we found ${topics.length} clear topics. Most delays stretch past a month — not just a few days.`;

  return { lead, support };
}

function scenarioReasons(
  scenario: BriefScenario | undefined,
  opportunities: Opportunity[],
  titles: Record<string, string>,
): { id: string; label: string; detail?: string }[] {
  if (!scenario?.opportunity_ids.length) return [];

  const byId = new Map(opportunities.map((row) => [row.opportunity_id, row]));
  return scenario.opportunity_ids
    .map((id) => byId.get(id))
    .filter((row): row is Opportunity => Boolean(row))
    .slice(0, 3)
    .map((row) => ({
      id: row.opportunity_id,
      label: reasonOptionLabel(row, titles),
      detail: humanImpact(row, scenario.id),
    }));
}

function humanImpact(row: Opportunity, scenarioId: string): string | undefined {
  if (scenarioId === "general") {
    const text = row.plain?.blocks_purchase_ever || row.plain?.delay_strength;
    return text ? shortProblem(easyCopy(text), 80) : undefined;
  }
  const text = row.plain?.delay_strength || row.plain?.waiting_past_30d;
  return text ? shortProblem(easyCopy(text), 80) : undefined;
}

function simplifyScenarioSummary(
  scenario: BriefScenario,
  titles: Record<string, string>,
): string {
  const raw = easyCopy(scenario.summary, titles);
  const firstSentence = raw.split(/(?<=[.!?])\s+/)[0] ?? raw;
  return firstSentence.length > 180 ? `${firstSentence.slice(0, 177).trim()}…` : firstSentence;
}

function scenarioAnswer(
  scenario: BriefScenario,
  reasons: { label: string }[],
  titles: Record<string, string>,
): string {
  if (scenario.id === "general" && reasons.length >= 2) {
    return `After saving, shoppers often never order because of “${reasons[0].label}” and “${reasons[1].label}” — plus similar blockers.`;
  }
  if (scenario.id === "within_30d" && reasons.length) {
    const next = reasons[1] ? `, then “${reasons[1].label}”` : "";
    return `Buys most often slip past a month because of “${reasons[0].label}”${next}.`;
  }
  return simplifyScenarioSummary(scenario, titles);
}

export function buildScenarioCards(
  briefing: Briefing | undefined,
  opportunities: Opportunity[],
  titles: Record<string, string>,
): ScenarioCard[] {
  const scenarios = briefing?.scenarios ?? [];
  const general = scenarios.find((s) => s.id === "general");
  const within = scenarios.find((s) => s.id === "within_30d");

  const cards: ScenarioCard[] = [];

  if (general) {
    const reasons = scenarioReasons(general, opportunities, titles);
    cards.push({
      id: "general",
      question: "Will they buy the saved item at all?",
      answer: scenarioAnswer(general, reasons, titles),
      reasons,
    });
  }

  if (within) {
    const reasons = scenarioReasons(within, opportunities, titles);
    cards.push({
      id: "within_30d",
      question: "Will they buy within a month of saving?",
      answer: scenarioAnswer(within, reasons, titles),
      reasons,
    });
  }

  return cards;
}

export function startHereCopy(
  briefing: Briefing | undefined,
  opportunities: Opportunity[],
  titles: Record<string, string>,
): {
  id: string;
  title: string;
  why: string;
  facts: string[];
  idea: string | null;
  quote: string;
} | null {
  const first = briefing?.first_bet;
  if (!first) return null;

  const row = opportunities.find((o) => o.opportunity_id === first.opportunity_id);
  const title = reasonOptionLabel(row ?? ({ opportunity_id: first.opportunity_id, problem_one_liner: first.problem } as Opportunity), titles);

  const facts = [
    easyCopy(first.how_common, titles),
    easyCopy(first.delay_strength, titles),
    easyCopy(first.waiting_past_30d, titles),
  ].filter(Boolean);

  const idea = hypothesisToTest(
    row ?? ({ opportunity_id: first.opportunity_id, suggested_lever: first.lever } as Opportunity),
    titles,
  );
  const hasConcreteIdea = idea && !/read shopper quotes first/i.test(idea);

  const why =
    row?.plain?.delay_strength && row.plain.how_common
      ? `${easyCopy(row.plain.how_common, titles)}. ${easyCopy(row.plain.delay_strength, titles)}.`
      : easyCopy(first.why, titles);

  return {
    id: first.opportunity_id,
    title,
    why: simplifyWhy(why),
    facts,
    idea: hasConcreteIdea ? idea : null,
    quote: first.quote,
  };
}

function simplifyWhy(text: string): string {
  let out = text
    .replace(/treat volume as a loudness diagnostic rather than a conversion lever/gi, "it is talked about a lot, but fixing it may not quickly change buys within a month")
    .replace(/the 30-day mechanism is weaker or mixed/gi, "it does not always explain why people wait past a month")
    .replace(/this theme may delay a saved-item purchase/gi, "this can delay buying a saved item")
    .replace(/but the /gi, "but ");
  return easyCopy(out);
}

export function sourceSummary(corpus?: CorpusHealth): string | null {
  if (!corpus) return null;
  const parts = Object.entries(corpus.yield_by_source ?? {})
    .filter(([, row]) => row.relevant > 0)
    .sort((a, b) => b[1].relevant - a[1].relevant)
    .map(([source, row]) => {
      const label =
        source === "play" ? "Google Play" : source === "app_store" ? "App Store" : source === "youtube" ? "YouTube" : source;
      return `${row.relevant} from ${label}`;
    });
  if (!parts.length) return null;
  return parts.join(" · ");
}

export type SegmentChartRow = {
  id: string;
  name: string;
  value: number;
  n: number;
  quota: "primary" | "supplementary" | null;
};

const PRIMARY_SEGMENT_IDS = new Set(["deal_hunters", "repeat_shoppers"]);
const SUPPLEMENTARY_SEGMENT_IDS = new Set([
  "first_time",
  "budget_salary",
  "occasion_office",
  "occasion_wedding",
  "occasion_festive",
  "genz_youth",
  "parents",
]);

export function segmentQuotaTier(id: string): SegmentChartRow["quota"] {
  if (PRIMARY_SEGMENT_IDS.has(id)) return "primary";
  if (SUPPLEMENTARY_SEGMENT_IDS.has(id)) return "supplementary";
  return null;
}

export function buildSegmentChartRows(segments: DemographicSegment[] | undefined): SegmentChartRow[] {
  if (!segments?.length) return [];
  return [...segments]
    .sort((a, b) => b.share - a.share)
    .map((segment) => ({
      id: segment.id,
      name: segment.label,
      value: Math.round(segment.share * 1000) / 10,
      n: segment.n,
      quota: segmentQuotaTier(segment.id),
    }));
}
