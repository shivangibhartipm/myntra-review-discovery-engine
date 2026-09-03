import type { BriefQuestion } from "@/lib/types";

export type ShareRow = {
  name: string;
  value: number;
};

/** Pull "% of comments" style evidence into chart rows; leave the rest as notes. */
export function splitShareEvidence(evidence: string[]): { shares: ShareRow[]; notes: string[] } {
  const shares: ShareRow[] = [];
  const notes: string[] = [];
  const seen = new Set<string>();

  for (const raw of evidence) {
    const line = raw.trim();
    if (!line) continue;
    const parsed = parseShareLine(line);
    if (!parsed) {
      notes.push(line);
      continue;
    }
    const key = `${parsed.name.toLowerCase()}|${parsed.value}`;
    if (seen.has(key)) continue;
    seen.add(key);
    shares.push(parsed);
  }

  shares.sort((a, b) => b.value - a.value || a.name.localeCompare(b.name));
  return { shares, notes };
}

export function questionHasShareChart(question: BriefQuestion | undefined): boolean {
  if (!question?.evidence?.length) return false;
  return splitShareEvidence(question.evidence).shares.length > 0;
}

function parseShareLine(line: string): ShareRow | null {
  const patterns: RegExp[] = [
    // "fit: 32.8% of comments about this" / "saving for later: 6.8% of wishlist-related comments"
    /^(.+?):\s*(?:about\s+)?(\d+(?:\.\d+)?)\s*%(?:\s+of\b.*)?$/i,
    // "Share of people comparing options: 1.1%"
    /^(Share of .+?):\s*(\d+(?:\.\d+)?)\s*%$/i,
    // "Waiting for a sale shows up in about 1.7% of these comments"
    /^(.+?)\s+shows up in about\s+(\d+(?:\.\d+)?)\s*%/i,
    // "Saving for later / on impulse: about 6.8%"
    /^(.+?):\s*about\s+(\d+(?:\.\d+)?)\s*%$/i,
    // "… — Most comments… (100.0%)"
    /^(.+?)\s+[—-]\s+.+\((\d+(?:\.\d+)?)\s*%\)\s*$/i,
    // "category:myntra_app (n=61): … (0.0%) — …"
    /^([^—]+?)\s*\(n=\d+\):\s*.*?\((\d+(?:\.\d+)?)\s*%\)/i,
  ];

  for (const pattern of patterns) {
    const match = line.match(pattern);
    if (!match) continue;
    const value = Number(match[2]);
    if (!Number.isFinite(value)) continue;
    const name = cleanLabel(match[1]);
    if (!name) continue;
    return { name, value: Math.round(value * 10) / 10 };
  }
  return null;
}

function cleanLabel(raw: string): string {
  let name = raw
    .replace(/^Consistent need:\s*/i, "")
    .replace(/^Often mentioned,\s*weaker for buying:\s*/i, "")
    .replace(/\s+of (wishlist-related )?comments.*$/i, "")
    .replace(/\s+of these comments.*$/i, "")
    .replace(/\s*[—-].*$/, "")
    .trim();

  // Prefer the clue for segment lines like "category:myntra_app (n=61): Few comments…"
  const clue = name.match(/^([^:]+(?::[^\s(]+)?)/);
  if (clue && /^(category|platform|occasion|segment):/i.test(clue[1])) {
    name = clue[1];
  }

  if (name.length > 42) {
    name = `${name.slice(0, 40).trim()}…`;
  }
  return name;
}
