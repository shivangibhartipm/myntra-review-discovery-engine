import Link from "next/link";
import { DualCharts } from "@/components/DualCharts";
import { TopicQuotes } from "@/components/TopicQuotes";
import { loadBoard, loadOpportunity, loadTopicQuotes } from "@/lib/data";
import { titleMap } from "@/lib/plainLanguage";
import { buildTopicBrief, pickTopicQuotes } from "@/lib/topicInsights";
import { notFound } from "next/navigation";

export default async function OpportunityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const row = loadOpportunity(id);
  if (!row) notFound();
  const board = loadBoard();
  const titles = titleMap(board?.opportunities || [row]);
  const brief = buildTopicBrief(row, titles);
  const quotes = pickTopicQuotes(loadTopicQuotes(id, row.quotes), 5);

  return (
    <div className="space-y-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-myntra-muted">
        <Link className="text-myntra-pink" href="/?tab=bets">
          Topic
        </Link>
        <span className="mx-2">/</span>
        Details
      </p>

      <section className="overflow-hidden rounded-sm bg-gradient-to-br from-[#fff4f6] to-white shadow-card">
        <div className="p-6">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-myntra-pink">Topic summary</p>
          <h1 className="mt-2 text-2xl font-bold leading-snug text-myntra-ink md:text-3xl">{brief.title}</h1>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-myntra-muted">{brief.summary}</p>
          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {brief.stats.map((stat) => (
              <div key={stat.label} className="rounded-sm border border-[#ffd6df] bg-white px-3 py-3">
                <p className="text-[10px] font-bold uppercase tracking-wide text-myntra-muted">{stat.label}</p>
                <p className="mt-1 text-sm leading-relaxed text-myntra-ink">{stat.value}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <TopicQuotes quotes={quotes} />

      <section className="grid gap-3 md:grid-cols-2">
        <InsightCard title="Within a month of saving" body={brief.withinMonth} foot={brief.waitsPastMonth} />
        <InsightCard title="Will they ever buy?" body={brief.everBuy} />
      </section>

      <div className="grid gap-3 sm:grid-cols-2">
        <TagCard title="Why they save" items={brief.jobs} empty="Not clearly stated in comments" />
        <TagCard
          title="Why the item is stuck"
          items={brief.stuckReasons.length ? brief.stuckReasons : brief.blockers}
          empty="Not clearly stated in comments"
          active
        />
      </div>

      <DualCharts prevalence={row.prevalence_relevant} metricRelevance={row.metric_relevance} />

      <section className="rounded-sm border border-myntra-pink/30 bg-[#fff4f6] p-5 shadow-card">
        <p className="text-[11px] font-bold uppercase tracking-wide text-myntra-pink">Idea to try</p>
        {brief.hasConcreteIdea ? (
          <>
            <p className="mt-2 text-lg font-semibold leading-relaxed text-myntra-ink">{brief.idea}</p>
            <p className="mt-2 text-sm text-myntra-muted">A starting point for a test — not a proven fix yet.</p>
          </>
        ) : (
          <p className="mt-2 text-sm leading-relaxed text-myntra-muted">
            Read the shopper quotes above, then decide what product change or message to test.
          </p>
        )}
      </section>

      <div className="flex flex-wrap gap-2">
        <Link
          href="/?tab=bets"
          className="rounded-sm border border-myntra-ink px-4 py-2 text-xs font-bold uppercase tracking-wide"
        >
          Back to topics
        </Link>
        <Link
          href="/compare"
          className="rounded-sm bg-[#FF3F6C] px-4 py-2 text-xs font-bold uppercase tracking-wide text-white"
        >
          Compare with another topic
        </Link>
      </div>
    </div>
  );
}

function InsightCard({ title, body, foot }: { title: string; body: string; foot?: string }) {
  return (
    <article className="rounded-sm bg-white p-5 shadow-card">
      <p className="text-[11px] font-bold uppercase tracking-wide text-myntra-pink">{title}</p>
      <p className="mt-2 text-sm leading-relaxed text-myntra-ink">{body || "We need more comments to be sure."}</p>
      {foot ? <p className="mt-2 text-xs text-myntra-muted">{foot}</p> : null}
    </article>
  );
}

function TagCard({
  title,
  items,
  empty,
  active,
}: {
  title: string;
  items: string[];
  empty: string;
  active?: boolean;
}) {
  return (
    <article className="rounded-sm bg-white p-5 shadow-card">
      <p className="text-[11px] font-bold uppercase text-myntra-muted">{title}</p>
      {items.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {items.map((item) => (
            <span key={item} className={active ? "myntra-chip myntra-chip-active" : "myntra-chip"}>
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-sm text-myntra-muted">{empty}</p>
      )}
    </article>
  );
}
