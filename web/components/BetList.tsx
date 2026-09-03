"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Opportunity } from "@/lib/types";

type SortKey = "rank_90d" | "rank_12m" | "volume_rank";

export function BetList({ opportunities }: { opportunities: Opportunity[] }) {
  const [sort, setSort] = useState<SortKey>("rank_90d");

  const rows = useMemo(() => {
    return opportunities.slice().sort((a, b) => (a[sort] ?? 999) - (b[sort] ?? 999));
  }, [opportunities, sort]);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Opportunity areas to compare</h2>
          <p className="text-sm text-zinc-600">
            Ordered by likely effect on wishlist → purchase (including within 30 days). Switch to volume to see what is merely loud.
          </p>
        </div>
        <label className="text-sm">
          Order
          <select
            className="ml-2 border border-zinc-300 bg-white px-2 py-1"
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
          >
            <option value="rank_90d">Best bet for conversion (last 3 months)</option>
            <option value="rank_12m">Best bet over 12 months</option>
            <option value="volume_rank">Most talked about (volume)</option>
          </select>
        </label>
      </div>
      <ol className="space-y-3">
        {rows.map((row) => {
          const plain = row.plain;
          return (
            <li key={row.opportunity_id} className="border border-zinc-200 bg-white p-4">
              <p className="text-xs text-zinc-500">
                Conversion rank {row.rank_90d ?? "—"} · Volume rank {row.volume_rank ?? "—"}
                {row.single_source_warning ? " · mostly one source" : ""}
              </p>
              <h3 className="mt-1 font-medium">
                <Link className="underline decoration-zinc-400 underline-offset-2" href={`/opportunities/${row.opportunity_id}`}>
                  {row.problem_one_liner}
                </Link>
              </h3>
              <p className="mt-2 text-sm text-zinc-700">{row.delay_mechanism}</p>
              <ul className="mt-3 space-y-1 text-sm text-zinc-600">
                <li>Within a month · {plain?.delay_strength ?? "—"}</li>
                <li>Buy at all · {plain?.blocks_purchase_ever ?? plain?.delay_strength ?? "—"}</li>
                <li>{plain?.how_common ?? "—"}</li>
                <li>{plain?.waiting_past_30d ?? "—"}</li>
              </ul>
              {plain?.jobs.length || plain?.blockers.length ? (
                <p className="mt-2 text-xs text-zinc-500">
                  Why they save: {plain?.jobs.join(", ") || "—"} · What stops the buy: {plain?.blockers.join(", ") || "—"}
                </p>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
