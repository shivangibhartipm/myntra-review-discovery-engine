import fs from "fs";
import path from "path";
import type { BoardPayload, Opportunity, Quote } from "./types";

const DATA_FILE = path.join(process.cwd(), "public", "data", "opportunities.json");
const QUOTES_DIR = path.join(process.cwd(), "public", "data", "quotes");

export function loadBoard(): BoardPayload | null {
  if (!fs.existsSync(DATA_FILE)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(DATA_FILE, "utf8")) as BoardPayload;
}

export function loadOpportunity(id: string): Opportunity | null {
  const board = loadBoard();
  return board?.opportunities.find((row) => row.opportunity_id === id) ?? null;
}

export function loadTopicQuotes(opportunityId: string, inline: Quote[] = []): Quote[] {
  const seen = new Set<string>();
  const merged: Quote[] = [];

  for (const quote of inline) {
    const key = quote.doc_id || quote.quote;
    if (!quote.quote?.trim() || seen.has(key)) continue;
    seen.add(key);
    merged.push(quote);
  }

  if (fs.existsSync(QUOTES_DIR)) {
    for (const file of fs.readdirSync(QUOTES_DIR)) {
      if (!file.endsWith(".json")) continue;
      const raw = JSON.parse(fs.readFileSync(path.join(QUOTES_DIR, file), "utf8")) as Quote & {
        opportunity_id?: string;
      };
      if (raw.opportunity_id !== opportunityId) continue;
      const key = raw.doc_id || raw.quote;
      if (!raw.quote?.trim() || seen.has(key)) continue;
      seen.add(key);
      merged.push({
        doc_id: raw.doc_id,
        source: raw.source,
        observed_at: raw.observed_at,
        quote: raw.quote,
      });
    }
  }

  return merged;
}
