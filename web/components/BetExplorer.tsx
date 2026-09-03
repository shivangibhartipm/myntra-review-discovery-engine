"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Opportunity } from "@/lib/types";
import { easyCopy, filterBlockerLabel, filterJobLabel, sourceLabel } from "@/lib/plainLanguage";
import { mentionShareLabel, uniqueTopics } from "@/lib/compareInsights";

type FilterOption = { key: string; label: string };

export function BetExplorer({ opportunities }: { opportunities: Opportunity[] }) {
  const [job, setJob] = useState("");
  const [blocker, setBlocker] = useState("");
  const [source, setSource] = useState("");

  const catalog = useMemo(() => uniqueTopics(opportunities), [opportunities]);

  const jobOptions = useMemo(
    () =>
      Array.from(new Set(catalog.flatMap((o) => o.jobs)))
        .filter((key) => key && key !== "unknown")
        .sort()
        .map((key) => ({ key, label: filterJobLabel(key) })),
    [catalog],
  );
  const blockerOptions = useMemo(
    () =>
      Array.from(new Set(catalog.flatMap((o) => o.blockers)))
        .filter(Boolean)
        .sort()
        .map((key) => ({ key, label: filterBlockerLabel(key) })),
    [catalog],
  );
  const sourceOptions = useMemo(
    () =>
      Array.from(new Set(catalog.flatMap((o) => o.sources)))
        .filter(Boolean)
        .sort()
        .map((key) => ({ key, label: sourceLabel(key) })),
    [catalog],
  );

  const rows = useMemo(() => {
    return catalog
      .filter((o) => {
        if (job && !o.jobs.includes(job)) return false;
        if (blocker && !o.blockers.includes(blocker)) return false;
        if (source && !o.sources.includes(source)) return false;
        return true;
      })
      .slice()
      .sort((a, b) => (a.rank_90d ?? 999) - (b.rank_90d ?? 999));
  }, [catalog, job, blocker, source]);

  const hasFilters = Boolean(job || blocker || source);

  function clearFilters() {
    setJob("");
    setBlocker("");
    setSource("");
  }

  return (
    <section className="space-y-4">
      <div className="rounded-sm bg-white p-5 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <p className="text-sm font-bold text-myntra-ink">Filter topics</p>
          {hasFilters ? (
            <button
              type="button"
              onClick={clearFilters}
              className="text-xs font-bold uppercase tracking-wide text-myntra-pink hover:text-[#E03560]"
            >
              Clear filters
            </button>
          ) : null}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <FilterSelect label="Why they save" value={job} onChange={setJob} options={jobOptions} />
          <FilterSelect label="What stops the buy" value={blocker} onChange={setBlocker} options={blockerOptions} />
          <FilterSelect label="Where we heard this" value={source} onChange={setSource} options={sourceOptions} />
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {rows.map((row, index) => (
          <Link
            key={row.opportunity_id}
            href={`/opportunities/${row.opportunity_id}`}
            className="group rounded-sm bg-white p-4 shadow-card transition hover:shadow-lift"
          >
            <div className="flex items-start gap-2">
              <span className="rounded-sm bg-myntra-ink px-2 py-0.5 text-[11px] font-bold text-white">
                Wait rank #{index + 1}
              </span>
            </div>
            <h3 className="mt-2 font-bold text-myntra-ink group-hover:text-myntra-pink">{easyCopy(row.problem_one_liner)}</h3>
            <p className="mt-2 line-clamp-2 text-sm text-myntra-muted">{easyCopy(row.delay_mechanism)}</p>
            <div className="mt-3 flex flex-wrap gap-1">
              {row.jobs
                .filter((j) => j && j !== "unknown")
                .slice(0, 2)
                .map((j) => (
                  <span key={j} className="myntra-chip">
                    {filterJobLabel(j)}
                  </span>
                ))}
              {row.blockers.slice(0, 2).map((b) => (
                <span key={b} className="myntra-chip myntra-chip-active">
                  {filterBlockerLabel(b)}
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs text-myntra-muted">{mentionShareLabel(row)}</p>
          </Link>
        ))}
      </div>
      {!rows.length ? <p className="text-sm text-myntra-muted">Nothing matches these filters.</p> : null}
    </section>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: FilterOption[];
}) {
  if (!options.length) return null;
  return (
    <label className="block min-w-0">
      <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-wide text-myntra-muted">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-sm border border-myntra-line bg-white px-3 py-2.5 text-sm text-myntra-ink"
      >
        <option value="">All</option>
        {options.map((opt) => (
          <option key={opt.key} value={opt.key}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}
