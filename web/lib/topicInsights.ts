import type { Opportunity, Quote } from "@/lib/types";
import {  howOftenMentioned,
  hypothesisToTest,
  reasonOptionLabel,
  withinMonthImpact,
} from "@/lib/compareInsights";
import { easyCopy, filterBlockerLabel, filterJobLabel } from "@/lib/plainLanguage";

export type TopicBrief = {
  title: string;
  summary: string;
  stats: { label: string; value: string }[];
  withinMonth: string;
  everBuy: string;
  waitsPastMonth: string;
  jobs: string[];
  blockers: string[];
  stuckReasons: string[];
  idea: string;
  hasConcreteIdea: boolean;
};

export function buildTopicBrief(row: Opportunity, titles: Record<string, string>): TopicBrief {
  const idea = hypothesisToTest(row, titles);
  const hasConcreteIdea = Boolean(idea && !/read shopper quotes first/i.test(idea));

  const jobs = (row.plain?.jobs.length ? row.plain.jobs : row.jobs)
    .filter((j) => j && j !== "unknown")
    .map((j) => filterJobLabel(j));
  const blockers = (row.plain?.blockers.length ? row.plain.blockers : row.blockers).map((b) =>
    filterBlockerLabel(b),
  );

  const summaryParts = [
    easyCopy(row.plain?.how_common, titles),
    easyCopy(row.plain?.delay_strength, titles),
  ].filter(Boolean);

  return {
    title: reasonOptionLabel(row, titles),
    summary: summaryParts.join(". ") || easyCopy(row.problem_one_liner, titles),
    stats: [
      { label: "How often mentioned", value: howOftenMentioned(row) },
      { label: "Impact on buying within a month", value: withinMonthImpact(row) },
    ],
    withinMonth: easyCopy(row.plain?.delay_strength || row.plain?.waiting_past_30d, titles),
    everBuy: easyCopy(row.plain?.blocks_purchase_ever || row.plain?.delay_strength, titles),
    waitsPastMonth: easyCopy(row.plain?.waiting_past_30d, titles),
    jobs,
    blockers,
    stuckReasons: row.stuck_reasons?.length ? row.stuck_reasons : [],
    idea,
    hasConcreteIdea,
  };
}

const SAVED_ITEM_CONTEXT =
  /\b(wishlist(?:ed|ing)?|saved?\s+(?:item|for\s+later|product|dress|shoes|pair|it|this|that)|i saved\b|shortlist(?:ed|ing)?|bookmark(?:ed|ing)?|added\s+to\s+(?:wishlist|cart)|keep(?:ing)?\s+in\s+(?:wishlist|cart)|wait(?:ing)?\s+for\s+(?:sale|discount|offer|price\s+drop)|sale\s+(?:timing|season)|price\s+drop)\b/i;

function quoteHasSavedItemContext(text: string): boolean {
  return SAVED_ITEM_CONTEXT.test(text);
}

export function pickTopicQuotes(quotes: Quote[], limit = 5): Quote[] {
  const seen = new Set<string>();
  const picked: Quote[] = [];
  for (const quote of quotes) {
    const key = quote.doc_id || quote.quote.slice(0, 40);
    const text = quote.quote.trim();
    if (
      !text ||
      seen.has(key) ||
      text.length < 25 ||
      text.split(/\s+/).length < 4 ||
      !quoteHasSavedItemContext(text)
    )
      continue;
    seen.add(key);
    picked.push({ ...quote, quote: text });
    if (picked.length >= limit) break;
  }
  return picked;
}
