# Problem statement: Wishlist-to-purchase conversion

You are a Product Manager on the Growth team at Myntra.

Millions of users browse fashion products, save items they like, and add them to wishlists. A wishlist is a high-intent signal: the user has expressed interest but has not purchased.

Over time, users can accumulate dozens—or hundreds—of wishlisted products. Only a small share of those items become orders.

## Business goal

Primary metric: **Increase the percentage of users who purchase at least one item from their wishlist within 30 days of adding it.**

Also understand **wishlist → purchase in general** (whether a saved item ever becomes an order), so teams can separate calendar delays (sale/salary wait) from blockers that kill conversion altogether (fit, returns, price).

Improving these outcomes should raise purchase frequency, monetize existing demand, and capture value that is already sitting in wishlists.

The underlying user problem is **not** given. The work is to **discover** why saved items do not convert — both inside 30 days and overall — then rank opportunity areas that could move the metric.

---

## What to build

Build an **AI-powered review discovery engine** that analyzes public user feedback at scale.

The system must go beyond sentiment scores and review summaries. It should:

1. Collect and structure feedback from **free, public sources** (see below).
2. Filter for language about wishlists, saving, shortlisting, postponing, comparing, fit, price, reviews, and purchase hesitation.
3. Extract jobs and blockers (for example: bookmark vs genuine intent; waiting for a sale; size uncertainty).
4. Cluster themes into **opportunity areas**.
5. **Identify, quantify where possible, and compare** those areas by how likely they are to affect 30-day wishlist conversion.

### Questions the engine should help answer

- Why do users add fashion products to a wishlist?
- What prevents wishlisted products from being purchased, and what uncertainties remain after a user has found a product they like?
- What causes users to postpone a purchase past 30 days (within-30-day horizon)?
- How do users compare multiple shortlisted products?
- What information do they seek **outside Myntra** before buying?
- What roles do fit, size, styling, price, reviews, occasion, and social validation play?
- When is the wishlist real purchase intent vs a bookmark?
- How do these behaviors differ across segments (where the text allows inference)?
- Which unmet needs show up consistently, and which are loud but weakly tied to this metric?

---

## Data: free public sources

Use **mostly free sources**. Prefer official public APIs, RSS feeds, and pages that allow public collection. Do not rely on paid social listening tools, paid review APIs, or gated datasets. Respect rate limits, terms of use, and do not store personal identifiers beyond what is needed for analysis.

### Primary (start here)

| Source | Why it matters | Typical free access |
| --- | --- | --- |
| Google Play reviews | Volume on app UX, returns, size charts, sale-period failures | Public listing / community scrapers |
| Apple App Store reviews | iOS UX, payments, trust | Public RSS / listing pages |
| Reddit | Closest to “should I buy / which of these / waiting for sale” | Reddit public API |
| YouTube comments on hauls and Myntra reviews | Fit, “looks different in person,” occasion dressing | YouTube Data API (free quota) |

### Secondary (use if primary coverage is thin)

| Source | Why it matters | Typical free access |
| --- | --- | --- |
| Public Myntra product reviews and Q&A (sampled) | Fit, fabric, photo mismatch—post-shortlist uncertainty | Public product pages only; sample, do not crawl the catalog |
| Quora, Mouthshut, Trustpilot | Returns, authenticity, support—blockers after save | Public pages |
| Competitor store reviews (Ajio, Amazon Fashion, Nykaa Fashion, Meesho) | Where users go to price-check or size-check before buying | Same free store listing pattern as Myntra apps |

### Deprioritize unless a free API is actually usable

Instagram, Facebook groups, private Discords/Telegrams, and X/Twitter are expensive or closed. Skip them unless a public, free endpoint is available without login walls.

**Priority if time or quota is limited:** Play + App Store (scale) → Reddit + YouTube (why people wait) → stratified PDP review samples in a few high-wishlist categories.

---

## How much history to collect

Fashion is seasonal and sale-driven. Collect enough to cover a full year of occasions and sale events, then overweight recent text so the product recommendations match current app and policy.

| Layer | Window | Purpose |
| --- | --- | --- |
| Primary corpus | **Last 12 months** | Full seasonal cycle and multiple sale events |
| Recency slice | **Last 90 days** | Current UX, policy, and catalog; use this to decide what to build now |
| Optional trend check | **18–24 months, sampled** | Only to see if a theme is new or worsening—not a second full dump |
| Product page reviews | **Last 6–12 months** per sampled category | Older fit reviews go stale if the product changes |

Do not aim for five years of reviews. Extra history adds noise more than insight.

Volume over extra years: take **all app-store reviews in 12 months**; take **hundreds of high-signal Reddit threads and YouTube videos**, not every unrelated comment; take **category-stratified PDP samples** (for example a few thousand reviews across ethnic wear, western wear, and footwear), not the whole catalog.

You will not join a review to a specific wishlist add. Collect talk that explains **decisions that take weeks**: waiting for a discount, salary cycle, more reviews, a friend’s opinion, or a store try-on.

---

## Success criteria for the engine

A useful output is a **ranked set of opportunity areas**, each with:

- The user problem in one sentence
- Evidence (quotes + counts or shares of relevant mentions)
- How it delays or blocks purchase **within 30 days of wishlist add**
- Who it seems to hit (if segment clues exist)
- Why it may or may not be the best lever vs other themes (for example, delivery complaints can be frequent but weakly causal for *wishlist* conversion compared with “I am waiting for End of Reason Sale”)

The engine fails if it only labels reviews positive/negative or produces a generic summary of “users care about quality and price.”
