"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ShareRow } from "@/lib/evidenceShares";

const PINK = "#FF3F6C";
const INK = "#282C3F";
const WASH = ["#FF3F6C", "#282C3F", "#F26A8D", "#535766", "#FF8FA8", "#7E818C"];

export function EvidenceSharesChart({
  shares,
  title = "Share of comments",
}: {
  shares: ShareRow[];
  title?: string;
}) {
  if (!shares.length) return null;
  const height = Math.max(180, 48 + shares.length * 36);
  const max = Math.max(...shares.map((s) => s.value), 1);
  const domainMax = Math.min(100, Math.max(10, Math.ceil(max / 10) * 10));

  return (
    <div className="mt-5 rounded-sm border border-myntra-line bg-myntra-wash/40 p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-myntra-muted">{title}</p>
      <p className="mt-1 text-xs text-myntra-muted">Percent of related shopper comments</p>
      <div style={{ height }} className="mt-2 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={shares} layout="vertical" margin={{ top: 4, right: 28, left: 4, bottom: 4 }}>
            <CartesianGrid stroke="#E9E9EB" strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, domainMax]}
              tick={{ fontSize: 11, fill: INK }}
              tickFormatter={(v: number) => `${v}%`}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={128}
              tick={{ fontSize: 11, fill: INK }}
              interval={0}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,63,108,0.06)" }}
              formatter={(value: number) => [`${value}%`, "Share of comments"]}
              labelStyle={{ color: INK, fontWeight: 600 }}
              contentStyle={{ borderRadius: 2, borderColor: "#E9E9EB" }}
            />
            <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={14} name="Share">
              {shares.map((_, i) => (
                <Cell key={shares[i].name} fill={WASH[i % WASH.length] || PINK} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
