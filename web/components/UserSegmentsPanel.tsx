"use client";

import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DemographicSegment, Opportunity } from "@/lib/types";
import { reasonOptionLabel } from "@/lib/compareInsights";
import { buildSegmentChartRows, type SegmentChartRow } from "@/lib/overviewInsights";

const PINK = "#FF3F6C";
const INK = "#282C3F";
const WASH = ["#FF3F6C", "#282C3F", "#F26A8D", "#535766", "#FF8FA8", "#7E818C", "#FFB3C4", "#94969F", "#FFD6DF"];

export function UserSegmentsPanel({
  segments,
  opportunities,
  titles,
}: {
  segments?: DemographicSegment[];
  opportunities: Opportunity[];
  titles: Record<string, string>;
}) {
  const rows = buildSegmentChartRows(segments);
  if (!rows.length) return null;

  const byId = new Map(opportunities.map((row) => [row.opportunity_id, row]));
  const sortedSegments = [...(segments ?? [])].sort((a, b) => b.share - a.share);

  return (
    <section className="rounded-md border border-myntra-line bg-white p-5 shadow-card md:p-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="section-accent">
          <h3 className="text-sm font-bold uppercase tracking-wide text-myntra-ink">Shopper segments</h3>
          <p className="mt-1 max-w-2xl text-sm text-myntra-muted">
            Lifestyle and shopping cues in wishlist-related comments — use for survey quotas and validation.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-wide">
          <span className="rounded-full border border-myntra-pink bg-[#fff4f6] px-2.5 py-1 text-myntra-pink">Primary quota</span>
          <span className="rounded-full border border-myntra-line bg-myntra-wash px-2.5 py-1 text-myntra-muted">Supplementary</span>
        </div>
      </div>

      <SegmentShareChart rows={rows} />

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {sortedSegments.map((segment) => (
          <SegmentCard
            key={segment.id}
            segment={segment}
            quota={rows.find((row) => row.id === segment.id)?.quota ?? null}
            topics={segment.opportunity_ids
              .map((id) => byId.get(id))
              .filter((row): row is Opportunity => Boolean(row))
              .map((row) => ({
                id: row.opportunity_id,
                label: reasonOptionLabel(row, titles),
              }))}
          />
        ))}
      </div>
    </section>
  );
}

function SegmentShareChart({ rows }: { rows: SegmentChartRow[] }) {
  const height = Math.max(220, 56 + rows.length * 34);
  const max = Math.max(...rows.map((row) => row.value), 1);
  const domainMax = Math.min(100, Math.max(12, Math.ceil(max / 2) * 2));

  return (
    <div className="mt-5 rounded-sm border border-myntra-line bg-myntra-wash/40 p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-myntra-muted">Share of wishlist-related comments</p>
      <p className="mt-1 text-xs text-myntra-muted">Segments only appear when shoppers use explicit cues in public text.</p>
      <div style={{ height }} className="mt-2 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 36, left: 4, bottom: 4 }}>
            <CartesianGrid stroke="#E9E9EB" strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, domainMax]}
              tick={{ fontSize: 11, fill: INK }}
              tickFormatter={(value: number) => `${value}%`}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={148}
              tick={{ fontSize: 10, fill: INK }}
              interval={0}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,63,108,0.06)" }}
              formatter={(value: number, _name, item) => {
                const payload = item.payload as SegmentChartRow;
                return [`${value}% · n=${payload.n}`, "Share of comments"];
              }}
              labelStyle={{ color: INK, fontWeight: 600, fontSize: 12 }}
              contentStyle={{ borderRadius: 2, borderColor: "#E9E9EB", fontSize: 12 }}
            />
            <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={14} name="Share">
              {rows.map((row, index) => (
                <Cell
                  key={row.id}
                  fill={row.quota === "primary" ? PINK : WASH[index % WASH.length] || INK}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function SegmentCard({
  segment,
  quota,
  topics,
}: {
  segment: DemographicSegment;
  quota: SegmentChartRow["quota"];
  topics: { id: string; label: string }[];
}) {
  const sharePct = Math.round(segment.share * 1000) / 10;
  const thinCue = /thin in wishlist|wider corpus/i.test(segment.diff);

  return (
    <article className="rounded-sm border border-myntra-line bg-myntra-wash/30 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="text-sm font-bold text-myntra-ink">{segment.label}</h4>
        {quota ? (
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
              quota === "primary"
                ? "bg-[#fff4f6] text-myntra-pink"
                : "bg-white text-myntra-muted"
            }`}
          >
            {quota === "primary" ? "Primary quota" : "Supplementary"}
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-xs leading-relaxed text-myntra-muted">{segment.diff}</p>
      <p className="mt-3 text-xs font-semibold text-myntra-ink">
        {sharePct}% of comments
        <span className="font-normal text-myntra-muted"> · n={segment.n}</span>
        {thinCue ? <span className="font-normal text-myntra-muted"> · thin explicit cue</span> : null}
      </p>
      {topics.length ? (
        <ul className="mt-3 space-y-1">
          {topics.map((topic) => (
            <li key={topic.id}>
              <Link href={`/opportunities/${topic.id}`} className="text-xs font-semibold text-myntra-pink hover:underline">
                {topic.label}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-xs text-myntra-muted">No linked topic yet — validate with survey cuts.</p>
      )}
    </article>
  );
}
