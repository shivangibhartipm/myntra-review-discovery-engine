"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const PINK = "#FF3F6C";
const INK = "#282C3F";

export function DualCharts({
  prevalence,
  metricRelevance,
}: {
  prevalence: number | null;
  metricRelevance: number | null;
}) {
  const commonPct = Math.round((prevalence ?? 0) * 1000) / 10;
  const waitScore = metricRelevance ?? 0;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <ChartCard
        title="How many comments mention this"
        hint={`About ${commonPct}% of comments about saved items`}
        data={[{ name: "Comments", value: commonPct }]}
        max={100}
        fill={INK}
        format={(v) => `${v}%`}
      />
      <ChartCard
        title="How much it makes people wait"
        hint="1 = little wait · 5 = people clearly wait after saving"
        data={[{ name: "Waiting", value: waitScore }]}
        max={5}
        fill={PINK}
        format={(v) => String(v)}
      />
    </div>
  );
}

function ChartCard({
  title,
  hint,
  data,
  max,
  fill,
  format,
}: {
  title: string;
  hint: string;
  data: { name: string; value: number }[];
  max: number;
  fill: string;
  format: (v: number) => string;
}) {
  return (
    <div className="h-56 rounded-sm bg-white p-4 shadow-card">
      <p className="text-sm font-bold">{title}</p>
      <p className="mb-2 text-xs text-myntra-muted">{hint}</p>
      <ResponsiveContainer width="100%" height="72%">
        <BarChart data={data}>
          <CartesianGrid stroke="#E9E9EB" strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis domain={[0, max]} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => format(v)} />
          <Bar dataKey="value" fill={fill} radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
