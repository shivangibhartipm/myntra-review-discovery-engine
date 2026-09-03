"use client";

import Link from "next/link";
import type { Briefing } from "@/lib/types";

export function DiscoveryBrief({ briefing }: { briefing: Briefing }) {
  const first = briefing.first_bet;
  return (
    <div className="space-y-8">
      <p className="max-w-3xl text-base leading-relaxed text-zinc-700">{briefing.goal}</p>
      {first ? (
        <section className="border border-zinc-900 bg-white p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Test this first</p>
          <h2 className="mt-2 text-xl font-semibold">
            <Link className="underline decoration-zinc-400 underline-offset-2" href={`/opportunities/${first.opportunity_id}`}>
              {first.problem}
            </Link>
          </h2>
          <p className="mt-3 max-w-3xl text-zinc-700">{first.why}</p>
          <ul className="mt-3 space-y-1 text-sm text-zinc-600">
            <li>{first.delay_strength}</li>
            <li>{first.how_common}</li>
            <li>{first.waiting_past_30d}</li>
          </ul>
          <p className="mt-3 text-sm">
            <span className="font-medium">Possible test (not a roadmap):</span> {first.lever}
          </p>
          {first.quote ? <blockquote className="mt-4 border-l-2 border-zinc-400 pl-3 text-sm text-zinc-800">“{first.quote}”</blockquote> : null}
        </section>
      ) : null}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">What the feedback is saying</h2>
        <p className="text-sm text-zinc-600">
          Jobs (why they save) and blockers (what stops the buy) — not positive/negative scores.
        </p>
        <div className="space-y-3">
          {briefing.questions.map((item) => (
            <article key={item.id} className="border border-zinc-200 bg-white p-4">
              <h3 className="font-medium">{item.question}</h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-700">{item.answer}</p>
              {item.evidence.length ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-600">
                  {item.evidence.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              ) : null}
              {item.opportunity_ids.length ? (
                <p className="mt-2 text-xs text-zinc-500">
                  Related bets:{" "}
                  {item.opportunity_ids.map((id, i) => (
                    <span key={id}>
                      {i > 0 ? " · " : ""}
                      <Link className="underline" href={`/opportunities/${id}`}>
                        {id}
                      </Link>
                    </span>
                  ))}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
