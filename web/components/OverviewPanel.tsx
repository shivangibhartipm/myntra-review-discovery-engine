"use client";

import Link from "next/link";
import type { Briefing, CorpusHealth, Opportunity } from "@/lib/types";
import { titleMap } from "@/lib/plainLanguage";
import { uniqueTopics } from "@/lib/compareInsights";
import {
  buildHeadline,
  buildScenarioCards,
  sourceSummary,
  topReasons,
  topStuckReasonTags,
} from "@/lib/overviewInsights";
import { UserSegmentsPanel } from "@/components/UserSegmentsPanel";

export function OverviewPanel({
  briefing,
  opportunities,
  corpusHealth,
  onOpenBets,
}: {
  briefing?: Briefing;
  opportunities: Opportunity[];
  corpusHealth?: CorpusHealth;
  onOpenBets: () => void;
}) {
  const titles = titleMap(opportunities);
  const topicCount = uniqueTopics(opportunities).length;
  const commentCount = corpusHealth?.n_relevant ?? null;
  const headline = buildHeadline(opportunities, corpusHealth);
  const scenarios = buildScenarioCards(briefing, opportunities, titles);
  const ranked = topReasons(opportunities, 3);
  const stuckTags = topStuckReasonTags(corpusHealth, 6);
  const sources = sourceSummary(corpusHealth);

  return (
    <div className="space-y-6">
      <section className="dashboard-hero-glow relative overflow-hidden rounded-md border border-[#ffd6df]/50 p-6 shadow-lift md:p-8">
        <div className="pointer-events-none absolute -right-6 top-0 h-40 w-40 rounded-full bg-myntra-pink/10 blur-3xl" />
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-myntra-pink">At a glance</p>
        <h2 className="mt-2 max-w-3xl text-2xl font-bold leading-snug tracking-tight text-myntra-ink md:text-[1.75rem]">
          {headline.lead}
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-myntra-muted md:text-base">{headline.support}</p>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          {commentCount != null ? (
            <StatPill label="Comments read" value={commentCount.toLocaleString()} tone="pink" icon="comments" />
          ) : null}
          <StatPill label="Topics found" value={String(topicCount)} tone="ink" icon="topics" />
          {ranked[0] ? (
            <StatPill label="#1 reason" value={ranked[0].label} wide tone="gold" icon="top" />
          ) : null}
        </div>
        {sources ? (
          <p className="mt-5 inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1.5 text-xs text-myntra-muted backdrop-blur-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-myntra-pink" />
            Sources: {sources}
          </p>
        ) : null}
      </section>

      {scenarios.length ? (
        <section className="space-y-4">
          <div className="section-accent">
            <h3 className="text-sm font-bold uppercase tracking-wide text-myntra-ink">Two questions shoppers face</h3>
            <p className="mt-1 text-sm text-myntra-muted">Same saved item — different time horizons.</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {scenarios.map((scenario) => (
              <article
                key={scenario.id}
                className={`group relative overflow-hidden rounded-md border bg-white p-5 shadow-card transition-shadow hover:shadow-lift ${
                  scenario.id === "within_30d" ? "border-[#ffd6df]" : "border-myntra-line"
                }`}
              >
                <div
                  className={`absolute inset-y-0 left-0 w-1 ${
                    scenario.id === "within_30d"
                      ? "bg-gradient-to-b from-myntra-pink to-[#ff8fa8]"
                      : "bg-gradient-to-b from-myntra-ink to-myntra-muted"
                  }`}
                />
                <div className="pl-2">
                  <p className="inline-flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-myntra-pink">
                    <ScenarioIcon id={scenario.id} />
                    {scenario.id === "within_30d" ? "Within a month" : "Ever buy?"}
                  </p>
                  <h4 className="mt-1 text-base font-bold text-myntra-ink">{scenario.question}</h4>
                  <p className="mt-2 text-sm leading-relaxed text-myntra-muted">{scenario.answer}</p>
                  {scenario.reasons.length ? (
                    <ol className="mt-4 space-y-2">
                      {scenario.reasons.map((reason, index) => (
                        <li key={reason.id} className="flex gap-3 rounded-md bg-myntra-wash/60 p-2 text-sm transition-colors group-hover:bg-myntra-wash">
                          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white text-xs font-bold text-myntra-pink shadow-sm ring-1 ring-[#ffd6df]">
                            {index + 1}
                          </span>
                          <div>
                            <Link href={`/opportunities/${reason.id}`} className="font-semibold text-myntra-ink hover:text-myntra-pink">
                              {reason.label}
                            </Link>
                            {reason.detail ? <p className="mt-0.5 text-xs text-myntra-muted">{reason.detail}</p> : null}
                          </div>
                        </li>
                      ))}
                    </ol>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {stuckTags.length ? (
        <section className="rounded-md border border-myntra-line bg-white p-5 shadow-card md:p-6">
          <div className="section-accent">
            <h3 className="text-sm font-bold uppercase tracking-wide text-myntra-ink">Why saved items get stuck</h3>
            <p className="mt-1 text-sm text-myntra-muted">
              Behavioral tags in shopper comments — not just “wishlist” mentions.
            </p>
          </div>
          <ul className="mt-5 flex flex-wrap gap-2">
            {stuckTags.map((tag, index) => (
              <li
                key={tag.label}
                className="rounded-full border border-[#ffd6df] bg-gradient-to-r from-[#fff4f6] to-white px-3 py-1.5 text-xs font-semibold text-myntra-ink transition-transform hover:-translate-y-0.5 hover:shadow-sm"
                style={{ animationDelay: `${index * 40}ms` }}
              >
                {tag.label}
                {tag.sharePct > 0 ? <span className="ml-1 font-normal text-myntra-pink">· {tag.sharePct}%</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {ranked.length ? (
        <section className="rounded-md border border-myntra-line bg-white p-5 shadow-card md:p-6">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div className="section-accent">
              <h3 className="text-sm font-bold uppercase tracking-wide text-myntra-ink">Top reasons people wait</h3>
              <p className="mt-1 text-sm text-myntra-muted">Ranked by how much they delay buying within a month.</p>
            </div>
            <button
              type="button"
              onClick={onOpenBets}
              className="rounded-full bg-[#fff4f6] px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-myntra-pink transition-colors hover:bg-myntra-pink hover:text-white"
            >
              See all {topicCount} topics →
            </button>
          </div>
          <ol className="mt-5 space-y-3">
            {ranked.map((reason) => (
              <li
                key={reason.id}
                className="rounded-md border border-myntra-line/80 bg-myntra-wash/30 p-4 transition-all hover:border-[#ffd6df] hover:bg-white hover:shadow-sm"
              >
                <div className="flex flex-wrap items-start gap-3">
                  <span
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white shadow-sm ${
                      reason.rank === 1 ? "bg-myntra-pink" : reason.rank === 2 ? "bg-myntra-ink" : "bg-myntra-muted"
                    }`}
                  >
                    {reason.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link href={`/opportunities/${reason.id}`} className="font-semibold text-myntra-ink hover:text-myntra-pink">
                        {reason.label}
                      </Link>
                      <Link
                        href={`/opportunities/${reason.id}`}
                        className="shrink-0 rounded-full border border-myntra-pink px-3 py-1 text-xs font-semibold text-myntra-pink transition-colors hover:bg-myntra-pink hover:text-white"
                      >
                        Details
                      </Link>
                    </div>
                    <p className="mt-1 text-xs text-myntra-muted">
                      {reason.mentionPct != null ? `Mentioned in ~${reason.mentionPct}% of comments` : "Mentioned in comments"}
                      {reason.waitsPastMonth ? " · often past a month" : ""}
                    </p>
                    {reason.mentionPct != null ? (
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-myntra-line">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-myntra-pink to-[#ff8fa8]"
                          style={{ width: `${Math.min(reason.mentionPct, 100)}%` }}
                        />
                      </div>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <UserSegmentsPanel
        segments={briefing?.demographic_segments}
        opportunities={opportunities}
        titles={titles}
      />
    </div>
  );
}

function StatPill({
  label,
  value,
  wide,
  tone,
  icon,
}: {
  label: string;
  value: string;
  wide?: boolean;
  tone: "pink" | "ink" | "gold";
  icon: "comments" | "topics" | "top";
}) {
  const tones = {
    pink: "border-[#ffd6df] from-[#fff4f6] to-white text-myntra-pink",
    ink: "border-myntra-line from-myntra-wash/80 to-white text-myntra-ink",
    gold: "border-[#ffe8a3] from-[#fffbeb] to-white text-[#b8860b]",
  };

  return (
    <div
      className={`rounded-md border bg-gradient-to-br px-4 py-3 shadow-sm transition-transform hover:-translate-y-0.5 hover:shadow-md ${tones[tone]} ${wide ? "sm:col-span-1" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] font-bold uppercase tracking-wide opacity-80">{label}</p>
        <StatIcon kind={icon} tone={tone} />
      </div>
      <p className={`mt-1 font-bold ${wide ? "text-sm leading-snug" : "text-2xl tracking-tight"}`}>{value}</p>
    </div>
  );
}

function StatIcon({ kind, tone }: { kind: "comments" | "topics" | "top"; tone: "pink" | "ink" | "gold" }) {
  const colors = { pink: "#FF3F6C", ink: "#282C3F", gold: "#FFC107" };
  const stroke = colors[tone];
  if (kind === "comments") {
    return (
      <svg className="h-5 w-5 shrink-0 opacity-70" viewBox="0 0 20 20" fill="none" aria-hidden>
        <path d="M4 5.5h12M4 10h8M4 14.5h10" stroke={stroke} strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (kind === "topics") {
    return (
      <svg className="h-5 w-5 shrink-0 opacity-70" viewBox="0 0 20 20" fill="none" aria-hidden>
        <rect x="3" y="3" width="6" height="6" rx="1.5" stroke={stroke} strokeWidth="1.5" />
        <rect x="11" y="3" width="6" height="6" rx="1.5" stroke={stroke} strokeWidth="1.5" />
        <rect x="3" y="11" width="6" height="6" rx="1.5" stroke={stroke} strokeWidth="1.5" />
        <rect x="11" y="11" width="6" height="6" rx="1.5" stroke={stroke} strokeWidth="1.5" />
      </svg>
    );
  }
  return (
    <svg className="h-5 w-5 shrink-0 opacity-70" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path d="M10 3.5l1.8 3.6 4 .6-2.9 2.8.7 4-3.6-1.9-3.6 1.9.7-4L4.2 7.7l4-.6L10 3.5z" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

function ScenarioIcon({ id }: { id: string }) {
  if (id === "within_30d") {
    return (
      <svg className="h-4 w-4 text-myntra-pink" viewBox="0 0 16 16" fill="none" aria-hidden>
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M8 4.5v4l2.5 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg className="h-4 w-4 text-myntra-pink" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M3 8.5l3.5 3.5L13 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
