# Users want the item but a concrete blocker stops checkout because they are unsure about size or fit before ordering a saved item.

One-pager for wishlist → purchase (within 30 days and overall). Hypothesis only — not a committed roadmap.

### 4. Users want the item but a concrete blocker stops checkout because they are unsure about size or fit before ordering a saved item.

- Id: `intent_blocked_fit`
- How it delays conversion: Fit uncertainty stops checkout of an otherwise intended saved item within 30 days.
- Within 30 days: This often makes people wait more than a month
- Wishlist → purchase (in general): This often keeps a saved item from becoming an order
- How common: Less common, but still shows up (3.4%)
- Waiting past 30 days: Some comments here say people wait more than a month (44.4%)
- Source mix: play:1.0
- Job mix: intent_blocked:0.8889; shortlist_compare:0.1111 · Blocker mix: fit:0.5; fabric_quality:0.125; photo_mismatch:0.125; price:0.125; size_chart:0.125
- Suggested lever (hypothesis only): Fit confidence on saved items (size recs, chart clarity)
- vs next theme: intent_blocked_fit outranks unknown_competitor_check for a buy within 30 days of save (recent 90 days): higher 30-day delay score (4 vs 3); lower share waiting past 30 days (0.44 vs 0.67).
