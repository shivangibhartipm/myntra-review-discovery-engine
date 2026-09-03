"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { Briefing, CorpusHealth, Opportunity } from "@/lib/types";
import { BetExplorer } from "@/components/BetExplorer";
import { OverviewPanel } from "@/components/OverviewPanel";
import { QuestionPanel } from "@/components/QuestionPanel";
import { easyCopy } from "@/lib/plainLanguage";
import { uniqueTopics } from "@/lib/compareInsights";

type Tab = "overview" | "questions" | "bets";

export function Dashboard({
  message,
  briefing,
  opportunities,
  corpusHealth,
  initialTab,
}: {
  message: string | null;
  briefing?: Briefing;
  opportunities: Opportunity[];
  corpusHealth?: CorpusHealth;
  initialTab: Tab;
}) {
  const router = useRouter();
  const [tab, setTabState] = useState<Tab>(initialTab);

  useEffect(() => {
    setTabState(initialTab);
  }, [initialTab]);

  function setTab(next: Tab) {
    setTabState(next);
    router.replace(next === "overview" ? "/" : `/?tab=${next}`, { scroll: false });
  }
  const tabs: { id: Tab; label: string; hint: string }[] = [
    { id: "overview", label: "Overview", hint: "What to look at first" },
    { id: "questions", label: "Questions", hint: "Simple answers from shoppers" },
    { id: "bets", label: "Topics", hint: "Browse and filter" },
  ];

  const counts = useMemo(
    () => ({
      bets: uniqueTopics(opportunities).length,
      questions: briefing?.questions.length ?? 0,
    }),
    [opportunities, briefing?.questions.length],
  );

  return (
    <div className="space-y-6">
      <div className="dashboard-hero-glow relative overflow-hidden rounded-md border border-[#ffd6df]/60 p-5 shadow-lift md:p-6">
        <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-myntra-pink/10 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-10 left-1/4 h-24 w-24 rounded-full bg-myntra-ink/5 blur-2xl" />
        <div className="relative">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-myntra-pink px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-white">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" />
              Live insights
            </span>
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-myntra-muted">
              Wishlist → purchase
            </span>
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-myntra-ink md:text-3xl">
            What&apos;s blocking saved items from becoming orders
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-myntra-muted">
            Ranked themes from real shopper comments — price timing, recall, fit, and more.
          </p>
          {message ? (
            <p className="mt-3 inline-flex rounded-full border border-[#ffd6df] bg-white/80 px-3 py-1.5 text-xs font-semibold text-myntra-pink backdrop-blur-sm">
              {easyCopy(message)}
            </p>
          ) : null}
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto rounded-md bg-white/90 p-1.5 shadow-card backdrop-blur-sm">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`group min-w-[9.5rem] flex-1 rounded-md px-4 py-3 text-left transition-all duration-200 ${
              tab === item.id
                ? "bg-gradient-to-br from-[#fff0f3] to-white text-myntra-pink shadow-sm ring-1 ring-[#ffd6df]"
                : "text-myntra-muted hover:bg-myntra-wash hover:text-myntra-ink"
            }`}
          >
            <span className="flex items-center gap-2">
              <TabIcon id={item.id} active={tab === item.id} />
              <span className="block text-sm font-bold uppercase tracking-wide">{item.label}</span>
            </span>
            <span className="mt-1 block pl-6 text-xs font-normal opacity-90">
              {item.hint}
              {item.id === "bets" ? ` · ${counts.bets}` : ""}
              {item.id === "questions" ? ` · ${counts.questions}` : ""}
            </span>
          </button>
        ))}
      </div>
      {tab === "overview" ? (
        <OverviewPanel
          briefing={briefing}
          opportunities={opportunities}
          corpusHealth={corpusHealth}
          onOpenBets={() => setTab("bets")}
        />
      ) : null}
      {tab === "questions" ? <QuestionPanel briefing={briefing} opportunities={opportunities} /> : null}
      {tab === "bets" ? <BetExplorer opportunities={opportunities} /> : null}
    </div>
  );
}

function TabIcon({ id, active }: { id: Tab; active: boolean }) {
  const className = `h-4 w-4 shrink-0 ${active ? "text-myntra-pink" : "text-myntra-muted group-hover:text-myntra-ink"}`;
  if (id === "overview") {
    return (
      <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden>
        <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
        <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
        <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
        <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }
  if (id === "questions") {
    return (
      <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden>
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M6.2 6.1a2 2 0 0 1 3.7.8c0 1.2-1.5 1.4-1.5 2.6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="8" cy="12" r="0.75" fill="currentColor" />
      </svg>
    );
  }
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M2 4.5h12M2 8h8M2 11.5h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
