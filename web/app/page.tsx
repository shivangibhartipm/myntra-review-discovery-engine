import { Dashboard } from "@/components/Dashboard";
import { loadBoard } from "@/lib/data";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const params = await searchParams;
  const board = loadBoard();
  if (!board) {
    return (
      <div className="rounded-sm bg-white p-8 shadow-card">
        <p className="font-bold text-myntra-ink">Insights aren’t ready yet</p>
        <p className="mt-2 text-sm text-myntra-muted">Ask your team to refresh the dashboard data.</p>
      </div>
    );
  }
  const tab = params.tab === "questions" || params.tab === "bets" ? params.tab : "overview";
  return (
    <Dashboard
      message={board.message}
      briefing={board.briefing}
      opportunities={board.opportunities}
      corpusHealth={board.corpus_health}
      initialTab={tab}
    />
  );
}
