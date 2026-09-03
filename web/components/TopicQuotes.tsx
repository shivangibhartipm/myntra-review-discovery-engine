import type { Quote } from "@/lib/types";
import { sourceLabel } from "@/lib/plainLanguage";

export function TopicQuotes({ quotes }: { quotes: Quote[] }) {
  if (!quotes.length) {
    return (
      <section className="rounded-sm bg-white p-5 shadow-card">
        <p className="text-[11px] font-bold uppercase tracking-wide text-myntra-pink">What shoppers said</p>
        <p className="mt-3 text-sm text-myntra-muted">
          No clear quotes matched this topic yet. The pattern still shows up across many comments — check back after
          the next data refresh.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-sm bg-white p-5 shadow-card">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wide text-myntra-pink">What shoppers said</p>
          <p className="mt-1 text-sm text-myntra-muted">Real comments that match this topic.</p>
        </div>
        <p className="text-xs font-semibold text-myntra-muted">{quotes.length} shown</p>
      </div>
      <ul className="mt-4 space-y-3">
        {quotes.map((quote) => (
          <li key={`${quote.doc_id}-${quote.quote.slice(0, 24)}`} className="rounded-sm border border-myntra-line bg-myntra-wash p-4">
            <p className="text-sm leading-relaxed text-myntra-ink">“{quote.quote}”</p>
            <p className="mt-2 text-xs text-myntra-muted">
              {sourceLabel(quote.source)}
              {quote.observed_at ? ` · ${formatDate(quote.observed_at)}` : ""}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
