# Architecture: AI-powered review discovery engine

This document is the phase-wise system design for the engine specified in [`problemstatement.md`](./problemstatement.md). It is written for engineering and product: what to build, in what order, with which artifacts, and how to know a phase is done.

## 1. Purpose

**North-star metric:** increase the percentage of users who purchase at least one item from their wishlist within **30 days** of adding it.

The engine does **not** start from a known user problem. It discovers why saved items stall, then **ranks opportunity areas** by how likely they are to move that metric.

It fails if the output is only sentiment labels or a generic summary such as “users care about quality and price.”

### What the engine must do

1. Collect and structure feedback from **free, public sources**.
2. Filter for language about wishlists, saving, shortlisting, postponing, comparing, fit, price, reviews, and purchase hesitation.
3. Extract **jobs** and **blockers** (bookmark vs genuine intent; waiting for a sale; size uncertainty; and similar).
4. Cluster themes into **opportunity areas**.
5. Identify, quantify where possible, and **compare** those areas by likely effect on 30-day wishlist conversion.
6. Present ranked opportunities so a Growth PM can choose the next bet (see Phase 6).

### Questions each phase should help answer

| Discovery question | Primary phases |
| --- | --- |
| Why do users add fashion products to a wishlist? | 3, 4, 5 |
| What stops wishlisted products from being purchased? | 3, 4, 5 |
| What uncertainties remain after a user has found a product they like? | 2, 3 |
| What causes users to postpone a purchase past 30 days? | 3, 5 |
| How do users compare multiple shortlisted products? | 2, 3, 4 |
| What information do they seek **outside Myntra** before buying? | 1 (source mix), 3, 4 |
| Roles of fit, size, styling, price, reviews, occasion, social validation | 3, 4 |
| When is the wishlist real purchase intent vs a bookmark? | 3, 5 |
| How do behaviors differ across segments (when text allows)? | 3, 5 |
| Which unmet needs are consistent vs loud but weakly tied to the metric? | 5, 6 |

---

## 2. Constraints (non-negotiable)

| Constraint | Implication |
| --- | --- |
| **Mostly free sources** | Official public APIs, RSS, and pages that allow public collection. No paid social listening, paid review APIs, or gated datasets. |
| **Free models only** | All NLP/LLM inference uses **local open-weight models** (default: Ollama). No paid LLM APIs (OpenAI, Anthropic, paid Gemini, etc.). |
| **Rate limits and terms of use** | Collectors are polite, retry with backoff, persist checkpoints, and stop when a source forbids use. |
| **Minimal PII** | Do not store names, emails, handles, or user IDs beyond what analysis requires. Hash or drop author identifiers after ingest. |
| **No join to a specific wishlist add** | Public text cannot be linked to a Myntra wishlist event. Infer **decision delays that take weeks**, not user-level conversion. |
| **Fashion seasonality** | Corpus windows are 12 months + 90-day recency overweight, not “as much history as possible.” |
| **Metric fidelity over NLP novelty** | Ranking must separate **volume** from **30-day conversion relevance**. |

**Internal funnel data** (wishlist add → PDP → size chart → reviews tab → price-drop → purchase in 30 days) is **out of band**: ask Growth analytics for it to size opportunities later. The public engine finds **why**; funnel data finds **how big**. Architecture should leave a hook (opportunity IDs) for that join, not depend on it for v1.

---

## 3. System overview

```text
                    ┌─────────────────────────────────────────────────────────┐
                    │                     Orchestrator                         │
                    │  run id, phase flags, quotas, source registry            │
                    └──────────────────────────┬──────────────────────────────┘
                                               │
     Phase 1              Phase 2               Phase 3              Phase 4
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Collectors  │───▶│  Relevance   │───▶│  Extract     │───▶│  Cluster     │
│  (per source)│    │  filter      │    │  jobs +      │    │  opportunity │
│              │    │              │    │  blockers    │    │  areas       │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │                   │
        ▼                   ▼                   ▼                   ▼
   raw_documents        relevant_docs       claims /           opportunity
   + source meta        + relevance         structured         clusters
                          score               records
                                               │
                    Phase 5                    ▼              Phase 6              Phase 7
                    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
                    │  Quantify,   │───▶│  Insight     │───▶│  Deploy      │
                    │  compare,    │    │  delivery    │    │  (Vercel)    │
                    │  rank        │    │  (board +    │    │              │
                    └──────────────┘    │   exports)   │    └──────────────┘
                                        └──────────────┘
```

**Logical stores** (implementation can be SQLite → Postgres; files for blobs):

| Store | Contents |
| --- | --- |
| `raw_documents` | Immutable ingest: text, source, collected_at, observed_at, url/id (hashed), rating if any |
| `document_enrichment` | Relevance, jobs, blockers, segments, embeddings, cluster assignment |
| `opportunity_areas` | Ranked themes with scores, quotes, comparison notes |
| `runs` | Pipeline run metadata, source quotas, filter rates, model versions |

**Runtime split:** Phases 0–5 run in **Python**. Phase 6 lite is a static report from that pipeline; the interactive board is **Next.js + React + TypeScript** reading `opportunity_areas` (exported as JSON). Phase 7 deploys only the `web/` app to **Vercel**. See Phases 6 and 7.

---

## 4. Design principles

1. **Jobs, not sentiment.** Classify each snippet into user jobs and blockers. Sentiment is an optional feature, never the product.
2. **Filter before you model.** Most Play Store text is app bugs and delivery. Ranking on the unfiltered corpus will promote loud, weakly causal themes.
3. **Two clocks.** Score every opportunity on the **12-month** corpus (season + sales) and the **90-day** slice (what to build now). Default product view is 90 days.
4. **Traceability.** Every opportunity must point at document IDs and verbatim quotes. No ungrounded LLM summaries as the source of truth.
5. **Compare, don’t list.** Phase 5 exists so “delivery complaints” can lose to “waiting for End of Reason Sale” on *this* metric.
6. **Idempotent phases.** Re-running a phase with the same run config should upsert, not duplicate. Collectors checkpoint by source cursor / date.
7. **Fail closed on PII and ToS.** Drop fields; do not “just store them for later.”

---

## 5. Canonical record (all phases)

Minimum fields after Phase 1. Later phases add columns; they do not invent a second document identity.

| Field | Notes |
| --- | --- |
| `doc_id` | Stable hash of source + native id or URL + observed timestamp |
| `source` | `play` \| `app_store` \| `reddit` \| `youtube` \| `pdp` \| `quora` \| `mouthshut` \| `trustpilot` \| `competitor_store` |
| `source_native_id` | Opaque; do not treat as a person identifier in exports |
| `url` | Optional; may be dropped in exports |
| `observed_at` | Review/post/comment date (analysis clock) |
| `collected_at` | Ingest time |
| `text` | Normalized UTF-8 body (title + body concatenated where useful) |
| `lang` | Detected; keep `en` and `hi`/`hinglish` if quality is good; drop others unless volume is high |
| `rating` | If the source has stars |
| `thread_id` | Reddit/YouTube parent, for context without storing usernames |
| `product_or_category` | If known (PDP sample, sometimes title) |
| `corpus_layer` | `primary_12m` \| `recency_90d` \| `trend_18_24m` \| `pdp_6_12m` |

**Do not persist:** author display name, email, avatar URL, IP, or unhashed user ids.

---

## 6. Phase 0 — Foundations

**Goal:** runnable project, shared contracts, source registry, and evaluation stubs so later phases do not invent incompatible schemas.

### Scope

- Repository layout (collect / filter / extract / cluster / rank / present).
- Config: date windows, source enablement, rate-limit budgets, **Ollama model tags** (`qwen2.5:7b`, `nomic-embed-text`).
- `runs` table and logging (counts in, counts out, error rates).
- Source registry: adapter interface (`fetch_page`, `normalize`, `respect_robots_or_tos`).
- Gold-set folder (empty at first): 50–100 labeled snippets for relevance and job/blocker tags.
- Decision: storage (recommend SQLite for local MVP, Postgres if multi-user).

### Time windows (from the problem statement)

| Layer | Window | Purpose | Collection rule |
| --- | --- | --- | --- |
| Primary corpus | Last **12 months** | Season + multiple sale events | Default for app stores: **all** reviews in window |
| Recency slice | Last **90 days** | Current UX, policy, catalog | Overweight in ranking and UI default |
| Optional trend | **18–24 months**, sampled | Theme new vs worsening | Sample only; not a second full dump |
| PDP reviews | Last **6–12 months** per sampled category | Fit/photo; products change | Stratified sample, not full catalog |

### Done when

- One fake or tiny collector can write a valid `raw_documents` row.
- Config encodes 12-month and 90-day cutoffs from `collected_at` vs `observed_at`.
- PII policy is documented in code comments / this file and enforced in the normalizer.

### Out of scope

- Production LLM serving, auth, multi-tenant SaaS.

---

## 7. Phase 1 — Collect and structure

**Goal:** a dated, source-attributed corpus that can explain **week-scale decisions** (sale wait, salary cycle, more reviews, friend’s opinion, store try-on)—not a five-year dump.

### Source priority

If time or quota is limited, stop after the current tier is healthy.

| Tier | Sources | Why |
| --- | --- | --- |
| **P0** | Google Play, Apple App Store | Scale: app UX, returns, size charts, sale-period failures, payments, trust |
| **P1** | Reddit public API; YouTube Data API (haul / Myntra review videos) | Closest to “should I buy / which of these / waiting for sale”; fit and occasion |
| **P2** | Sampled public Myntra PDP reviews + Q&A (few categories, not catalog crawl) | Post-shortlist uncertainty: fit, fabric, photo mismatch |
| **P3** | Quora, Mouthshut, Trustpilot; competitor store listings (Ajio, Amazon Fashion, Nykaa Fashion, Meesho) | Outside-Myntra checks; authenticity and support blockers |
| **Skip unless a free public API exists** | Instagram, Facebook groups, private Discord/Telegram, X/Twitter | Closed or expensive |

### Volume targets (prefer volume in-window over extra years)

| Source | Target |
| --- | --- |
| App stores | All reviews in 12 months |
| Reddit + YouTube | Hundreds of **high-signal** threads/videos, not every unrelated comment |
| PDP | Category-stratified, e.g. a few thousand reviews across ethnic wear, western wear, footwear |

### Collector design

Each source is an **adapter**:

1. Authenticate only with free public credentials (e.g. Reddit app, YouTube API key).
2. Page until the `observed_at` window is covered or quota is exhausted.
3. Normalize into the canonical record.
4. Checkpoint (`source`, `cursor` or `last_observed_at`).
5. Deduplicate on `doc_id`.

**Query / listing strategy (illustrative, implement as config):**

- Play / App Store: Myntra app listing; optional competitor apps in P3.
- Reddit: search and subreddit pulls for wishlist, sale wait, “Myntra or Ajio”, size, haul, wedding/office occasion—not generic India news.
- YouTube: video IDs from search (`Myntra haul`, sale haul, honest review); comments only on those videos.
- PDP: **sampled** product URLs in chosen categories; hard cap; no recursive catalog crawl.

### Done when

- P0 (and P1 if keys exist) populate `raw_documents` with 12-month coverage and a 90-day flag.
- Duplicate rate is low; language and dates are populated.
- A run report shows counts by source and by corpus layer.

### Risks

- RSS/App Store pagination gaps; Play scraper breakage → prefer official/community tools that stay ToS-safe.
- YouTube quota → cap videos, not “all comments on the internet.”
- Hindi / Hinglish mixed with English → keep; do not drop as “low quality” without a language policy.

---

## 8. Phase 2 — Relevance filter

**Goal:** keep text that can speak to **save / shortlist / postpone / compare / hesitate**, and drop the mass of unrelated 1-star delivery and login bugs—unless that text clearly kills checkout of a **saved** item.

### Why this phase exists

Unfiltered clustering will surface “app crash during sale” and “delivery late.” Those can be real, but they are often **weakly causal for 30-day wishlist conversion** compared with “I am waiting for EORS.” The filter defines the **relevant mention** denominator used in Phase 5.

### Method (two-stage, cheap then precise)

1. **Lexical / heuristic gate** (fast, recall-oriented): keywords and patterns for wishlist, save, later, sale, EORS, shortlist, vs, compare, size, fit, return, fake, price drop, salary, try in store, reviews not enough, occasion, wedding, office look, etc.
2. **Classifier or LLM judge** (precision-oriented) on the gated set: `relevant_to_wishlist_conversion` with a short rationale and a 0–1 score.
3. **Keep-if-borderline:** sale-wait and compare language with no explicit “wishlist” word still counts (bookmark behavior).

**Negative class examples:** pure OTP/login, unrelated brand hate with no purchase-delay content, spam, one-word comments.

**Positive class examples:** “added to wishlist until sale,” “confused between two kurtas,” “won’t buy until I know the size,” “looks different in haul video so waiting.”

### Outputs

| Field | Meaning |
| --- | --- |
| `is_relevant` | Boolean after threshold |
| `relevance_score` | 0–1 |
| `relevance_reasons` | Tags: `wishlist_language`, `postpone`, `compare`, `fit_uncertainty`, `price_wait`, `external_validation`, `returns_trust`, … |
| `filter_version` | For eval and reruns |

Store **both** filtered and unfiltered counts. Phase 5 uses **relevant** as the primary base; unfiltered volume is a diagnostic (loudness).

### Done when

- Gold set precision/recall is measured (even if initially modest).
- Filter yield is reported: e.g. “Play 8% relevant, Reddit 40% relevant.”
- A human can sample 20 relevant and 20 rejected docs and agree the policy.

### Fail condition

- Downstream ranking uses all Play reviews equally with Reddit “should I buy” threads.

---

## 9. Phase 3 — Extract jobs and blockers

**Goal:** structured claims per relevant document, not a paragraph summary.

### Taxonomies (v1; extend only with evidence)

**Jobs (why the list exists):**

| Job | Typical language | Link to 30-day conversion |
| --- | --- | --- |
| `bookmark_later` | saving for later, when I have money | Delay, often past 30 days |
| `wait_for_sale` | EORS, discount, price drop | Systematic clock expiry |
| `shortlist_compare` | between these two, which is better | Choice paralysis |
| `intent_blocked` | love it but size / return / fake / price | Convertible if blocker is removed |
| `occasion_social` | wedding, office, will this look good | Confidence, not missing SKU |
| `impulse_park` | liked the pic | Low true intent |

**Blockers / uncertainty types:** fit, size chart, photo mismatch, fabric/quality, price, sale timing, review volume/trust, authenticity, returns, delivery/checkout of saved item, styling/occasion, social validation, competitor price/size check.

**Segment clues (only if explicit or high-confidence):** gender presentation in text, occasion, price sensitivity, iOS vs Android (from source), category. Never invent demographics.

### Extraction design

- Input: relevant docs (+ optional parent thread title for Reddit/YouTube).
- Output: one or more **claims** per doc:

```text
claim: {
  doc_id,
  jobs[],
  blockers[],
  postponement_beyond_30d: yes | no | unknown,
  outside_myntra_info_seeking: bool,
  segment_clues[],
  confidence,
  evidence_span  // substring or quote
}
```

- Prefer **span-grounded** extraction (quote must appear in `text`).
- Batch LLM with a strict JSON schema; fallback rules for obvious lexical cases (`eors`, `wishlist`).
- Optional: sentiment as a feature on the claim, not a top-level insight.

### Done when

- Each relevant doc has at least a job or a blocker (or an explicit `unknown`).
- Spot-check: bookmark vs intent is not collapsed into “negative sentiment.”
- Exportable table: `doc_id`, jobs, blockers, quote.

---

## 10. Phase 4 — Cluster into opportunity areas

**Goal:** 5–12 **opportunity areas** a PM can name in a sentence—not 200 micro-topics and not 3 mega-buckets (“price,” “quality,” “app”).

### Method

1. Embed claim text (or relevant doc text + job/blocker tags).
2. Cluster (e.g. HDBSCAN / agglomerative on embeddings). Tune toward **interpretable count**, not maximum silhouette.
3. **Name** each cluster with a one-sentence user problem, generated from top quotes + job/blocker histogram, then **human-editable**.
4. Merge duplicates (“size chart unclear” vs “don’t know my size”).
5. Split mixed clusters (sale-wait mixed with delivery).
6. Attach `representative_doc_ids` (diverse sources and dates, not only Play).

### Opportunity object (draft, unranked)

| Field | Requirement |
| --- | --- |
| `opportunity_id` | Stable slug after naming freeze |
| `problem_one_liner` | User problem in one sentence |
| `member_doc_ids` | Traceability |
| `job_mix` | Histogram of jobs in the cluster |
| `blocker_mix` | Histogram of blockers |
| `source_mix` | Prevents one source from defining the theme |

### Done when

- A reviewer can read 8 cluster names and not confuse them.
- Each cluster has quotes from more than one source **or** an explicit “single-source” warning.
- No cluster is named “miscellaneous” without a follow-up split or drop.

---

## 11. Phase 5 — Quantify, compare, rank

**Goal:** order opportunity areas by **likely effect on 30-day wishlist conversion**, not by mention count.

You cannot observe conversion. You **score proxies** and make the proxies visible.

### Metrics per opportunity (compute on relevant corpus unless noted)

| Metric | Definition | Use |
| --- | --- | --- |
| `prevalence_relevant` | Share of relevant docs (or claims) in this cluster | How common among in-scope talk |
| `prevalence_unfiltered` | Share of all docs | Loudness diagnostic |
| `recency_90d_share` | Fraction of cluster mass in last 90 days vs 12 months | What to build now vs seasonal |
| `postponement_rate` | Share of members tagged `postponement_beyond_30d = yes` | Direct metric link |
| `intent_vs_bookmark` | Mix of `intent_blocked` vs `bookmark_later` / `impulse_park` | Convertible vs low-intent |
| `multi_source_support` | Present in Reddit/YouTube vs only app-store | Robustness |
| `actionability` | Rubric: can Myntra change this in product, pricing, merchandising, or CX? | Rank penalty if not |
| `metric_relevance` | Rubric 1–5: how clearly this **delays or blocks purchase within 30 days of add** | Primary rank key |

**Illustrative composite (tunable, must be documented in config):**

```text
rank_score ≈
  w1 * metric_relevance
+ w2 * postponement_rate
+ w3 * prevalence_relevant
+ w4 * recency_boost(90d)
+ w5 * actionability
− w6 * loud_but_weak_penalty   # high unfiltered share, low metric_relevance
```

**Worked comparison the ranker must be able to express:** delivery complaints can have high `prevalence_unfiltered` and low `metric_relevance` for *wishlist* conversion; “waiting for End of Reason Sale” can have lower raw volume and higher `postponement_rate` / `metric_relevance`.

### Comparison artifact

For the top N opportunities, store a **pairwise or listwise note**: why A outranks B (evidence + scores). This becomes the “why it may or may not be the best lever” field.

### Segment splits

Only emit a segment slice when `n` exceeds a minimum (e.g. 30 relevant docs) and clues are explicit. Otherwise omit—do not guess.

### Done when

- Top 5–8 opportunities each have: one-sentence problem, evidence (quotes + counts/shares), 30-day delay mechanism, who (if allowed), comparison vs other themes.
- Rank order changes if you toggle “sort by volume” vs “sort by metric relevance” (proves the score is not just counts).
- Recency (90d) and primary (12m) ranks are both stored.

### Fail condition

- Rank equals “most 1-star Play reviews.”

---

## 12. Phase 6 — Insight delivery

**Goal:** Growth PMs can pick the next 30-day conversion bet without reading the warehouse.

This phase is the product surface of the engine, not a generic BI dump. The discovery pipeline stays in **Python**; the UI is a thin client over Phase 5 artifacts.

### UI stack

**Interactive product UI:** **Next.js (App Router) + React + TypeScript**.

| Layer | Choice | Role |
| --- | --- | --- |
| App | Next.js (App Router) | Board at `/`, detail at `/opportunities/[id]`, optional Route Handlers to serve artifacts |
| UI | React + TypeScript | Ranked table, filters, quote drawer, compare view |
| Style | Tailwind CSS | Flat table/card layout without a heavy component kit |
| Charts | Recharts | Two **separate** series: prevalence vs metric relevance (never one combined bar) |
| Tables | TanStack Table when the board grows | Client sort (rank vs volume) and column filters |

**Data contract:** Python writes `data/opportunities.json` (plus quote/snippet files keyed by `doc_id`). Next.js reads those files at build/request time or via a small API. No second application backend is required for v1.

**Phase 6 lite (before the app):** a **static ranked Markdown (or HTML) report** generated by the ranker. Adopt Next.js when filters, the 90-day vs 12-month toggle, and drill-in quotes are needed—not before Phase 5 exists.

**Do not use as the PM product UI**

| Option | Why not (for this surface) |
| --- | --- |
| Streamlit, Gradio, Dash | Fine for pipeline debug; weak routing, compare view, and stakeholder polish |
| Django/Flask templates | Duplicates Python in the UI while the board is a React-shaped product |
| Metabase, Tableau, Looker | Useful later for corpus-health SQL; not for quote-grounded opportunity cards |

### Primary UI: ranked opportunity board

- Default sort: Phase 5 `rank_score` on the **90-day** slice; toggle **12 months**.
- Each row: rank, one-liner, metric-relevance, prevalence (relevant), postponement signal, source mix, segment (if any).
- Filters: source, job, category, corpus layer.

### Opportunity detail

- Problem statement and **how it delays purchase within 30 days of wishlist add**.
- Prevalence vs conversion relevance as **two** measures (never one bar for both).
- Quote drawer: verbatim text, source, `observed_at`, `doc_id`.
- Job mix and blocker mix.
- Comparison paragraph vs the next-best theme.
- Suggested lever (hypothesis only): e.g. wishlist price-drop, fit confidence on saved items, compare-saved-items, social/occasion proof. Not a committed roadmap.

### Secondary surfaces

- **Compare view:** top opportunities side by side.
- **Corpus health:** collected vs relevant yield, last run, windows—trust, not the hero.
- **Exports:** JSON/CSV of opportunities; one-pager Markdown/PDF per opportunity for stakeholders.
- **Audit table:** tagged snippets for model review.

### What not to lead with

- Overall star rating or NPS.
- Unfiltered topic clouds.
- A single unranked “AI summary.”

### Done when

- A PM can answer “what should we test first for 30-day wishlist conversion?” from the board plus one detail page, with quotes they can defend.

---

## 13. Phase 7 — Deployment

**Goal:** ship the Phase 6 board to a stable, shareable URL so Growth PMs and stakeholders can use it without running the pipeline locally.

This phase deploys **only the Next.js dashboard** (`web/`). The Python collectors, Ollama jobs, and internal product docs stay off the hosting surface.

### Deployment model (Option A — chosen)

| Piece | Where it lives |
| --- | --- |
| **Git** | One GitHub repo for the full project |
| **Vercel** | One Vercel project linked to that repo |
| **Root Directory** | `web` (not the repo root) |
| **URL** | `https://<project>.vercel.app` (+ optional custom domain) |

**Why Option A:** simplest path for v1 — one deploy target, auto-redeploy on push to `main`, no second app or subdomain routing. A separate Vercel project for a wishlist **prototype** is a later decision (different repo or `prototype/` folder).

### What gets deployed

| Included | Excluded |
| --- | --- |
| `web/app/`, `web/components/`, `web/lib/` | Python pipeline (`collect/`, `filter/`, etc.) |
| `web/public/data/` (`opportunities.json`, quotes, corpus health) | `web/node_modules/`, `web/.next/` |
| `web/public/myntra-logo.png` and static assets | Local SQLite / `.db` files |
| Build output from `npm run build` | Internal docs listed in `.gitignore` (solution decision, survey analysis, hypotheses, etc.) |

The board reads JSON from `web/public/data/` at build/request time (`loadBoard()` in `web/lib/data.ts`). No application backend or env vars are required for v1.

### Vercel project settings

| Setting | Value |
| --- | --- |
| Framework Preset | Next.js |
| Root Directory | `web` |
| Build Command | `npm run build` |
| Install Command | `npm install` |
| Output Directory | `.next` (default) |
| Node.js | 20.x (default) |
| Environment variables | None for v1 |

### Release workflow

```text
1. Run pipeline (Phases 0–5) locally
2. Export / copy artifacts → web/public/data/
3. git add web/public/data/ … → commit → push to main
4. Vercel auto-builds and deploys
5. Smoke-test live URL (/, /compare, /health, /opportunities/[id])
```

**Data refresh:** updating the dashboard is a **content deploy** — commit new JSON under `web/public/data/`, not a pipeline run on Vercel.

### Pre-deploy checklist

- [ ] Git repo on GitHub; `web/public/data/opportunities.json` is committed
- [ ] Vercel **Root Directory** = `web`
- [ ] Logo and quote files present under `web/public/`
- [ ] `npm run build` succeeds locally (optional; Vercel build is authoritative)
- [ ] Internal strategy docs remain in `.gitignore` if they should not ship publicly

### Post-deploy verification

| Route | Expected |
| --- | --- |
| `/` | Overview with ranked topics and stats (not “Insights aren’t ready yet”) |
| `/?tab=questions` | Questions panel |
| `/?tab=bets` | Topics explorer |
| `/compare` | Compare view |
| `/health` | Data sources / corpus health |
| `/opportunities/[id]` | Opportunity detail with quotes |

### Custom domain (optional)

1. Vercel project → **Settings → Domains**
2. Add e.g. `wishlist-insights.yourcompany.com`
3. Configure DNS per Vercel instructions

### Operations

- **Auto-deploy:** push to `main` triggers production; use preview deployments for branches/PRs
- **Rollback:** Vercel → Deployments → promote a previous successful build
- **Secrets:** no API keys in the client bundle; if auth is added later, use Vercel env vars server-side only
- **Monitoring:** Vercel build logs; optional analytics on the project

### Done when

- Production URL loads the board with live data
- Stakeholders can open the link without cloning the repo or running `npm run dev`
- Documented root directory (`web`) and data refresh steps are followed on each pipeline export

### Out of scope (v1)

- Deploying the Python pipeline to a cloud runner (collectors stay local/CI optional)
- Multi-tenant auth, Postgres, or server-side API for the board
- Second Vercel project for a Myntra consumer-app prototype (future)
- Password protection (add via Vercel if needed for internal-only URLs)

---

## 14. Cross-cutting architecture

### Orchestration

- CLI or workflow: `run --phase collect|filter|extract|cluster|rank|present --sources play,reddit`.
- Phases 2–5 are functions of `run_id` + model versions; changing a prompt bumps `extract_version` and invalidates downstream caches.

### Models (free / local only)

All generation and embeddings run on **open-weight models on the developer machine**. Default runtime: [Ollama](https://ollama.com). Pin tags in `config.yaml` and log them on `runs`.

| Step | Model | Notes |
| --- | --- | --- |
| Language detect | `lingua` or `langdetect` (library, not an LLM) | Before any generation |
| Relevance | **Qwen 2.5 Instruct 7B** (`qwen2.5:7b`) after the lexical gate | JSON: `is_relevant`, score, tags |
| Extraction | **Same `qwen2.5:7b`** | Jobs, blockers, spans; usable on Hinglish. Move to **`qwen2.5:14b`** only if 7B fails the gold set. |
| Embedding | **nomic-embed-text** (Ollama) or local `BAAI/bge-small-en-v1.5` | Freeze this model across runs |
| Cluster naming | **Same Qwen 7B** (tiny volume) | Always human-edit the one-liners |
| Rank | None | Config weights only |

**Disallowed:** OpenAI, Anthropic, paid Google Gemini, paid Groq/Together/Fireworks, or any metered chat API. A vendor free trial is not a project dependency.

**Quality bar:** structured JSON; `evidence_span` must be a substring of `text`; gold-set checks. If local CPU is too slow, keep Ollama and a smaller tag (`qwen2.5:7b` or `llama3.2:3b` for relevance only) — do not add a paid API.

**Pull once:** `ollama pull qwen2.5:7b` and `ollama pull nomic-embed-text`.

### Evaluation

| Gate | Check |
| --- | --- |
| Relevance | Precision/recall on gold snippets |
| Extraction | Job/blocker agreement on gold |
| Ranking | Blind PM sort of 6 themes vs model rank; document disagreements |
| Grounding | Quote ⊆ document text (automated) |
| Leakage | No PII in exports (automated scan for emails/phones) |

### Ethics and compliance

- Public data only; robots/ToS per source.
- No deanonymization, no storing reviewer identities.
- Quotes in the UI may be shortened; full text stays in the audit store with access control if the app is multi-user.

### Operations

- Incremental collect (weekly) vs full 12-month backfill (once).
- 90-day overweight is a **query/rank** concern, not a delete of older primary corpus.
- Alert if a source adapter returns zero for N days (scraper/API break).

---

## 15. Delivery plan (build order)

| Phase | MVP (must ship) | Later |
| --- | --- | --- |
| 0 | Schema, config, run log | Postgres, auth |
| 1 | Play + App Store, 12 months | Reddit, YouTube, PDP sample, P3 sources |
| 2 | Heuristic + LLM/classifier relevance | Trained classifier, multilingual tuning |
| 3 | Jobs + blockers + 30-day postpone flag | Finer segment model |
| 4 | Embedding clusters + named opportunities | Human-in-the-loop merge UI |
| 5 | Prevalence + metric_relevance + rank | Funnel join, experiment design export |
| 6 | Static ranked Markdown/CSV (Phase 6 lite) | Next.js board, detail routes, compare view, one-pagers |
| 7 | Vercel deploy (`web/` root), smoke-test checklist | Custom domain, preview-branch policy, deploy auth |

**Recommended first vertical slice:** Phase 0 → Phase 1 (Play only, 90 days) → Phase 2 → Phase 3 → skip fancy clustering: **manual or simple group-by blocker** → Phase 5 scores → a **static ranked Markdown report** (Phase 6 lite). Then add App Store, Reddit, embeddings, the **Next.js** interactive board, and **Phase 7** deploy to Vercel.

---

## 16. Mapping to success criteria

| Success criterion | Where it is produced |
| --- | --- |
| User problem in one sentence | Phase 4 naming, shown in Phase 6 |
| Evidence (quotes + counts/shares) | Phases 3–5; quotes must be span-grounded |
| How it delays/blocks purchase within 30 days of add | Phase 3 `postponement_beyond_30d` + Phase 5 copy |
| Who it hits (if clues exist) | Phase 3 segment clues; Phase 5 min-n rule |
| Why it may or may not be the best lever vs other themes | Phase 5 comparison notes |
| Not mere sentiment / generic quality-and-price summary | Phases 2–5 design; Phase 6 home screen rules |
| Stakeholders can access the board without local setup | Phase 7 deploy |

---

## 17. Explicit non-goals

- Replacing Myntra’s internal review or CX dashboards.
- Predicting individual users’ conversion.
- Crawling the full Myntra catalog.
- Five-year review history as a quality signal.
- Paid social listening as a required input.
- Shipping features on the Myntra consumer app (the engine **recommends** levers; it does not implement wishlist UX).
- Paid LLM or embedding APIs.
