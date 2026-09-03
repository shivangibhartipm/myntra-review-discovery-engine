"use client";

import { useState } from "react";
import type { Quote } from "@/lib/types";
import { sourceLabel } from "@/lib/plainLanguage";

export function QuoteDrawer({ quotes }: { quotes: Quote[] }) {
  const [open, setOpen] = useState(true);
  if (!quotes.length) {
    return <p className="text-sm text-myntra-muted">No shopper quotes for this topic yet.</p>;
  }
  return (
    <section className="overflow-hidden rounded-sm bg-white shadow-card">
      <button
        type="button"
        className="flex w-full items-center justify-between px-5 py-3 text-left text-sm font-bold uppercase tracking-wide"
        onClick={() => setOpen((v) => !v)}
      >
        <span>Users in their words ({quotes.length})</span>
        <span className="text-myntra-pink">{open ? "Hide" : "Show"}</span>
      </button>
      {open ? (
        <ul className="space-y-3 border-t border-myntra-line px-5 py-4">
          {quotes.map((q) => (
            <li key={`${q.doc_id}-${q.quote.slice(0, 24)}`} className="rounded-sm bg-myntra-wash p-3 text-sm">
              <p className="text-myntra-ink">“{q.quote}”</p>
              <p className="mt-1 text-xs text-myntra-muted">
                {sourceLabel(q.source)} · {q.observed_at || "date unknown"}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
