import { loadBoard } from "@/lib/data";
import { phaseLabel, sourceLabel } from "@/lib/plainLanguage";

export default function HealthPage() {
  const board = loadBoard();
  const health = board?.corpus_health;
  if (!health) {
    return <p>Data quality details aren’t ready yet.</p>;
  }
  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-myntra-pink">Can we trust this?</p>
        <h1 className="mt-1 text-2xl font-bold md:text-3xl">Data quality</h1>
        <p className="mt-2 max-w-2xl text-sm text-myntra-muted">
          This page only shows whether we kept comments about saving and waiting. The Home page has the insights.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Comments collected" value={health.n_unfiltered} />
        <Stat label="About saved items" value={health.n_relevant} />
        <Stat
          label="Last update"
          value={phaseLabel(health.last_run?.phase)}
          sub={String(health.last_run?.started_at || "")}
        />
      </div>
      <div className="overflow-hidden rounded-sm bg-white shadow-card">
        <table className="w-full text-left text-sm">
          <thead className="bg-myntra-ink text-white">
            <tr>
              <th className="px-4 py-3 font-bold">Where comments came from</th>
              <th className="px-4 py-3 font-bold">All comments</th>
              <th className="px-4 py-3 font-bold">About saved items</th>
              <th className="px-4 py-3 font-bold">Share kept</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(health.yield_by_source || {}).map(([source, row]) => (
              <tr key={source} className="border-t border-myntra-line">
                <td className="px-4 py-3 font-semibold">{sourceLabel(source)}</td>
                <td className="px-4 py-3">{row.unfiltered}</td>
                <td className="px-4 py-3">{row.relevant}</td>
                <td className="px-4 py-3 text-myntra-pink">{pct(row.yield)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-sm bg-white p-4 shadow-card">
      <p className="text-[11px] font-bold uppercase text-myntra-muted">{label}</p>
      <p className="mt-1 text-xl font-bold">{value}</p>
      {sub ? <p className="mt-1 text-xs text-myntra-muted">{sub}</p> : null}
    </div>
  );
}

function pct(n: number) {
  if (n == null || Number.isNaN(n)) return "—";
  if (n <= 1) return `${Math.round(n * 1000) / 10}%`;
  return String(n);
}
