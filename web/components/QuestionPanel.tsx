"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Briefing, Opportunity } from "@/lib/types";
import { EvidenceSharesChart } from "@/components/EvidenceSharesChart";
import { splitShareEvidence } from "@/lib/evidenceShares";
import { easyCopy, questionTitle, shortProblem, titleMap } from "@/lib/plainLanguage";

export function QuestionPanel({
  briefing,
  opportunities = [],
}: {
  briefing?: Briefing;
  opportunities?: Opportunity[];
}) {
  const questions = briefing?.questions ?? [];
  const titles = titleMap(opportunities);
  const [active, setActive] = useState(questions[0]?.id ?? "");
  const current = questions.find((q) => q.id === active) ?? questions[0];
  const { shares, notes } = useMemo(
    () => splitShareEvidence(current?.evidence ?? []),
    [current?.evidence, current?.id],
  );

  if (!current) {
    return <p className="rounded-sm bg-white p-6 text-sm text-myntra-muted shadow-card">Answers aren’t ready yet.</p>;
  }
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="h-fit rounded-sm bg-white shadow-card lg:sticky lg:top-28">
          <p className="border-b border-myntra-line px-4 py-3 text-xs font-bold uppercase tracking-wide text-myntra-muted">
            Jump to a question
          </p>
          <ol>
            {questions.map((item, i) => {
              const title = questionTitle(item.id, item.question);
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setActive(item.id)}
                    className={`w-full border-l-4 px-4 py-3 text-left text-sm ${
                      item.id === current.id
                        ? "border-myntra-pink bg-[#fff4f6] font-semibold text-myntra-ink"
                        : "border-transparent text-myntra-muted hover:bg-myntra-wash"
                    }`}
                  >
                    <span className="mr-2 text-xs text-myntra-pink">{String(i + 1).padStart(2, "0")}</span>
                    {shortQ(title)}
                  </button>
                </li>
              );
            })}
          </ol>
        </aside>
        <article className="rounded-sm bg-white p-6 shadow-card">
          <p className="text-xs font-bold uppercase tracking-wide text-myntra-pink">From shopper comments</p>
          <h2 className="mt-2 text-xl font-bold text-myntra-ink">{questionTitle(current.id, current.question)}</h2>
          <p className="mt-4 text-sm leading-relaxed text-myntra-ink">{easyCopy(current.answer, titles)}</p>
          {shares.length ? (
            <EvidenceSharesChart
              shares={shares}
              title={chartTitleFor(current.id)}
            />
          ) : null}
          {notes.length ? (
            <ul className="mt-4 space-y-2">
              {notes.map((line) => (
                <li key={line} className="rounded-sm bg-myntra-wash px-3 py-2 text-sm text-myntra-muted">
                  {easyCopy(line, titles)}
                </li>
              ))}
            </ul>
          ) : null}
          {current.opportunity_ids.length ? (
            <div className="mt-5">
              <p className="text-xs font-bold uppercase tracking-wide text-myntra-muted">Related topics</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {current.opportunity_ids.map((id) => (
                  <Link
                    key={id}
                    href={`/opportunities/${id}`}
                    className="rounded-full border border-myntra-pink px-3 py-1 text-xs font-semibold text-myntra-pink"
                  >
                    {shortProblem(titles[id] || id, 48)}
                  </Link>
                ))}
              </div>
            </div>
          ) : null}
        </article>
      </div>
    </div>
  );
}

function chartTitleFor(id: string): string {
  const titles: Record<string, string> = {
    why_wishlist: "Why they save · share of comments",
    stops_purchase: "What blocks the buy · share of comments",
    postpone_30d: "Why they wait · share of comments",
    compare_shortlist: "Comparing options · share of comments",
    outside_myntra: "Checks outside Myntra · share of comments",
    roles: "Fit, price, and more · share of comments",
    intent_vs_bookmark: "Intent vs bookmark · share of comments",
    segments: "Shopper type · share of comments with an explicit cue",
    loud_vs_metric: "Unmet needs · share of comments",
  };
  return titles[id] || "Share of comments";
}

function shortQ(q: string) {
  const clean = q.replace(/\?$/, "");
  if (clean.length <= 58) return `${clean}?`;
  return `${clean.slice(0, 58).trim()}…?`;
}
