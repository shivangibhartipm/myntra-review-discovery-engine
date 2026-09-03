"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import type { Opportunity } from "@/lib/types";
import {
  buyAtAllImpact,
  compareSummary,
  howOftenMentioned,
  hypothesisToTest,
  mentionPriority,
  monthPriority,
  reasonOptionLabel,
  uniqueReasonOptions,
  waitsMoreThanMonth,
  whatShoppersSay,
  withinMonthImpact,
} from "@/lib/compareInsights";
import { easyCopy, titleMap } from "@/lib/plainLanguage";

export function ComparePicker({ opportunities }: { opportunities: Opportunity[] }) {
  const options = useMemo(() => uniqueReasonOptions(opportunities), [opportunities]);
  const titles = titleMap(options);
  const [left, setLeft] = useState(options[0]?.opportunity_id ?? "");
  const [right, setRight] = useState(options[1]?.opportunity_id ?? options[0]?.opportunity_id ?? "");

  useEffect(() => {
    const ids = options.map((o) => o.opportunity_id);
    setLeft((current) => (ids.includes(current) ? current : ids[0] ?? ""));
    setRight((current) => (ids.includes(current) ? current : ids[1] ?? ids[0] ?? ""));
  }, [options]);

  const a = options.find((o) => o.opportunity_id === left);
  const b = options.find((o) => o.opportunity_id === right);

  if (!options.length) {
    return <p>There are no reasons to compare yet.</p>;
  }

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-myntra-pink">Compare</p>
        <h1 className="mt-1 text-2xl font-bold md:text-3xl">Which reason should we fix first?</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-myntra-muted">
          Pick two reasons shoppers give for not buying saved items. See which one matters more for buying within a
          month — and which one people simply talk about more.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="rounded-sm bg-white p-3 text-sm shadow-card">
          <span className="text-[11px] font-bold uppercase text-myntra-muted">Reason 1</span>
          <select className="mt-1 w-full bg-transparent font-semibold" value={left} onChange={(e) => setLeft(e.target.value)}>
            {options.map((o) => (
              <option key={o.opportunity_id} value={o.opportunity_id}>
                {reasonOptionLabel(o, titles)}
              </option>
            ))}
          </select>
        </label>
        <label className="rounded-sm bg-white p-3 text-sm shadow-card">
          <span className="text-[11px] font-bold uppercase text-myntra-muted">Reason 2</span>
          <select
            className="mt-1 w-full bg-transparent font-semibold"
            value={right}
            onChange={(e) => setRight(e.target.value)}
          >
            {options.map((o) => (
              <option key={o.opportunity_id} value={o.opportunity_id}>
                {reasonOptionLabel(o, titles)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {a && b ? (
        <section className="rounded-sm border border-myntra-pink/30 bg-[#fff4f6] p-5">
          <p className="text-[11px] font-bold uppercase tracking-wide text-myntra-pink">Quick answer</p>
          <p className="mt-2 text-sm leading-relaxed text-myntra-ink">{compareSummary(a, b, titles)}</p>
        </section>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        {a ? <ReasonCard row={a} titles={titles} /> : null}
        {b ? <ReasonCard row={b} titles={titles} /> : null}
      </div>
    </div>
  );
}

function ReasonCard({ row, titles }: { row: Opportunity; titles: Record<string, string> }) {
  const name = easyCopy(row.problem_one_liner, titles);

  return (
    <article className="flex h-full flex-col rounded-sm bg-white p-5 shadow-card">
      <h2 className="text-lg font-bold leading-snug">
        <Link className="hover:text-myntra-pink" href={`/opportunities/${row.opportunity_id}`}>
          {name}
        </Link>
      </h2>

      <section className="mt-4 space-y-3 text-sm">
        <p className="text-[11px] font-bold uppercase tracking-wide text-myntra-muted">What shoppers say</p>
        <p className="leading-relaxed text-myntra-ink">{whatShoppersSay(row, titles)}</p>
      </section>

      <section className="mt-5 space-y-3 rounded-sm bg-myntra-wash p-4 text-sm">
        <p className="text-[11px] font-bold uppercase tracking-wide text-myntra-muted">Simple read</p>
        <Insight label="How often it comes up">{howOftenMentioned(row)}</Insight>
        <Insight label="Talked about">{mentionPriority(row)}</Insight>
        <Insight label="Buys within a month">{withinMonthImpact(row)}</Insight>
        <Insight label="Waits more than a month?">{waitsMoreThanMonth(row)}</Insight>
        <Insight label="Ever buys the saved item?">{buyAtAllImpact(row)}</Insight>
        <Insight label="If your goal is one month">{monthPriority(row)}</Insight>
      </section>

      <section className="mt-5 rounded-sm border border-myntra-line p-4">
        <p className="text-[11px] font-bold uppercase tracking-wide text-myntra-pink">Hypothesis to test</p>
        <p className="mt-2 text-sm leading-relaxed text-myntra-ink">{hypothesisToTest(row, titles)}</p>
        <p className="mt-2 text-xs text-myntra-muted">This is an idea to try — not a proven fix yet.</p>
      </section>
    </article>
  );
}

function Insight({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="font-semibold text-myntra-ink">{label}</p>
      <p className="mt-0.5 text-myntra-muted">{children}</p>
    </div>
  );
}
