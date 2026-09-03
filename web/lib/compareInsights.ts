import type { Opportunity } from "@/lib/types";
import { easyCopy, shortProblem } from "@/lib/plainLanguage";

const REASON_LABELS: Record<string, string> = {
  wait_for_sale_sale_timing: "Waiting for a sale",
  wait_for_sale_price: "Waiting for sale or price drop",
  unknown_price: "Price feels too high",
  bookmark_later_photo_mismatch: "Product looks different in photos",
  unknown_fit: "Fit or size is unclear",
  intent_blocked_fit: "Fit or size is unclear",
  unknown_returns: "Returns feel risky",
  intent_blocked_returns: "Returns block checkout",
  bookmark_later_price: "Saved because price is high",
  unknown_competitor_check: "Checking other apps first",
  unknown_fabric_quality: "Fabric or quality doubt",
  shortlist_compare_open: "Comparing saved options",
  shortlist_compare_review_volume_trust: "Not enough trusted reviews",
};

function reasonFamilyKey(row: Opportunity): string {
  const id = row.opportunity_id;
  const blockers = row.blocker_mix ?? {};
  const jobs = row.job_mix ?? {};

  if (id.startsWith("wait_for_sale") || blockers.sale_timing || jobs.wait_for_sale) {
    return "sale_wait";
  }
  if (blockers.photo_mismatch) return "photo_mismatch";
  if (blockers.price) return "price";
  if (blockers.returns) return "returns";
  if (blockers.fit || blockers.size_chart) return "fit";

  const blocker = topMixKey(row.blocker_mix);
  const job = topMixKey(row.job_mix, { skipUnknown: true });
  if (blocker) return blocker;
  if (job) return job;
  return id;
}

function topMixKey(mix: Record<string, number> | undefined, opts?: { skipUnknown?: boolean }): string | null {
  if (!mix) return null;
  let entries = Object.entries(mix);
  if (!entries.length) return null;
  if (opts?.skipUnknown) {
    const filtered = entries.filter(([key]) => key !== "unknown");
    if (filtered.length) entries = filtered;
  }
  return entries.sort((a, b) => b[1] - a[1])[0][0];
}

function normalizeLabel(text: string): string {
  return text
    .toLowerCase()
    .replace(/…/g, "")
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function labelsOverlap(a: string, b: string): boolean {
  const na = normalizeLabel(a);
  const nb = normalizeLabel(b);
  if (!na || !nb) return false;
  if (na === nb) return true;
  const shorter = na.length <= nb.length ? na : nb;
  const longer = na.length > nb.length ? na : nb;
  return shorter.length >= 18 && longer.startsWith(shorter);
}

export function uniqueReasonOptions(opportunities: Opportunity[]): Opportunity[] {
  const sorted = opportunities
    .slice()
    .sort((a, b) => (a.rank_90d ?? 99) - (b.rank_90d ?? 99) || (a.volume_rank ?? 99) - (b.volume_rank ?? 99));

  const picked: Opportunity[] = [];
  const seenFamilies = new Set<string>();

  for (const row of sorted) {
    const family = reasonFamilyKey(row);
    if (seenFamilies.has(family)) continue;

    const label = reasonOptionLabel(row);
    if (picked.some((existing) => labelsOverlap(reasonOptionLabel(existing), label))) continue;

    picked.push(row);
    seenFamilies.add(family);
  }

  return picked;
}

/** Same grouping as compare — one card per similar reason in the Topics tab. */
export const uniqueTopics = uniqueReasonOptions;

export function reasonOptionLabel(row: Opportunity, titles?: Record<string, string>): string {
  const preset = REASON_LABELS[row.opportunity_id];
  if (preset) return preset;
  return shortProblem(easyCopy(row.problem_one_liner, titles), 72);
}

export function mentionShareLabel(row: Opportunity): string {
  if (row.prevalence_relevant != null) {
    const pct = row.prevalence_relevant * 100;
    const formatted = Number.isInteger(pct) ? String(pct) : pct.toFixed(1);
    return `${formatted}% of comments mentioned this`;
  }
  const match = row.plain?.how_common?.match(/([\d.]+)%/);
  if (match) return `${match[1]}% of comments mentioned this`;
  return "";
}

export function howOftenMentioned(row: Opportunity): string {
  if (row.plain?.how_common) return easyCopy(row.plain.how_common);
  const pct = Math.round((row.prevalence_relevant ?? 0) * 100);
  if (pct >= 30) return `Comes up a lot — about ${pct} in every 100 comments.`;
  if (pct >= 15) return `Comes up fairly often — about ${pct} in every 100 comments.`;
  if (pct >= 5) return `Comes up sometimes — about ${pct} in every 100 comments.`;
  if (pct > 0) return `Comes up rarely — about ${pct} in every 100 comments.`;
  return "We do not have enough comments on this yet.";
}

export function waitsMoreThanMonth(row: Opportunity): string {
  if (row.plain?.waiting_past_30d) return easyCopy(row.plain.waiting_past_30d);
  const rate = row.postponement_rate ?? 0;
  if (rate >= 0.5) return "Yes — people often say they wait more than a month.";
  if (rate > 0) return "Sometimes — some people wait more than a month.";
  return "Not clearly — comments do not often say they wait more than a month.";
}

export function withinMonthImpact(row: Opportunity): string {
  return easyCopy(row.plain?.delay_strength) || "We need more comments to be sure.";
}

export function buyAtAllImpact(row: Opportunity): string {
  return (
    easyCopy(row.plain?.blocks_purchase_ever || row.plain?.delay_strength) ||
    "We need more comments to be sure."
  );
}

export function monthPriority(row: Opportunity): string {
  const rank = row.rank_90d;
  if (rank === 1) return "Best place to start if you want more buys within a month.";
  if (rank && rank <= 3) return "Strong reason to work on for buys within a month.";
  if (rank && rank <= 5) return "Worth fixing, but other reasons may matter more for the one-month goal.";
  return "Lower priority for the one-month goal.";
}

export function mentionPriority(row: Opportunity): string {
  const rank = row.volume_rank;
  if (rank === 1) return "The most talked-about reason in comments.";
  if (rank && rank <= 3) return "One of the most talked-about reasons.";
  if (rank && rank <= 6) return "Mentioned sometimes in comments.";
  return "Mentioned rarely in comments.";
}

export function compareSummary(
  a: Opportunity,
  b: Opportunity,
  titles: Record<string, string>,
): string {
  if (a.opportunity_id === b.opportunity_id) {
    return "Pick two different reasons to see how they differ.";
  }

  const aName = reasonOptionLabel(a, titles);
  const bName = reasonOptionLabel(b, titles);
  const aMonth = a.rank_90d ?? 99;
  const bMonth = b.rank_90d ?? 99;
  const aTalk = a.volume_rank ?? 99;
  const bTalk = b.volume_rank ?? 99;

  const parts: string[] = [];

  if (aMonth < bMonth) {
    parts.push(`If you want more buys within a month of saving, start with “${aName}”.`);
  } else if (bMonth < aMonth) {
    parts.push(`If you want more buys within a month of saving, start with “${bName}”.`);
  }

  if (aTalk < bTalk) {
    parts.push(`Shoppers talk about “${aName}” more often than “${bName}”.`);
  } else if (bTalk < aTalk) {
    parts.push(`Shoppers talk about “${bName}” more often than “${aName}”.`);
  }

  if (!parts.length) {
    return "These two reasons look similar in the comments we read. Use the cards below to choose.";
  }

  return parts.join(" ");
}

export function hypothesisToTest(row: Opportunity, titles: Record<string, string>): string {
  const lever = easyCopy(row.suggested_lever, titles).trim();
  if (!lever) return "Read shopper quotes first, then decide what to test.";
  if (/tbd|inspect quotes|hypothesis/i.test(lever)) {
    return "Read shopper quotes first, then decide what to test.";
  }
  return lever;
}

export function whatShoppersSay(row: Opportunity, titles: Record<string, string>): string {
  return easyCopy(row.delay_mechanism, titles) || easyCopy(row.problem_one_liner, titles);
}
