import type { Opportunity } from "@/lib/types";

const QUESTION_TITLES: Record<string, string> = {
  why_wishlist: "Why do users add fashion products to their wishlist?",
  stops_purchase:
    "What prevents wishlisted products from being purchased, and what uncertainties remain after users like an item?",
  postpone_30d: "What causes users to postpone a purchase?",
  compare_shortlist: "How do users compare multiple shortlisted products?",
  outside_myntra: "What information do users seek outside Myntra before purchasing?",
  roles: "What role do fit, size, styling, price, reviews, occasion and social validation play?",
  intent_vs_bookmark:
    "When do users use the wishlist as genuine purchase intent versus simply as a bookmarking mechanism?",
  segments: "How do these behaviors differ across user segments?",
  loud_vs_metric: "What unmet needs emerge consistently across user conversations?",
};

const SOURCE_LABELS: Record<string, string> = {
  play: "Google Play",
  app_store: "App Store",
  reddit: "Reddit",
  youtube: "YouTube",
};

const PHRASE_SWAPS: [RegExp, string][] = [
  [/theme-weighted talk/gi, "comments about this"],
  [/theme-weighted jobs/gi, "comments"],
  [/wishlist-related talk/gi, "comments about saved items"],
  [/wishlist-related share/gi, "share of comments about saved items"],
  [/strongly tied to missing a buy within 30 days of save/gi, "this often stops people from buying within a month"],
  [/strongly tied to missing a buy within a month of saving/gi, "this often stops people from buying within a month"],
  [/likely delays a buy within 30 days of save/gi, "this often makes people wait more than a month"],
  [/sometimes delays a buy; mixed with other motives/gi, "this sometimes makes people wait, along with other reasons"],
  [/often loud in reviews, weakly tied to 30-day wishlist conversion/gi, "people mention this a lot, but it doesn’t always delay buying"],
  [/most of this theme is people delaying past 30 days/gi, "most comments here say people wait more than a month"],
  [/some of this theme is people delaying past 30 days/gi, "some comments here say people wait more than a month"],
  [/little explicit “i’ll wait past 30 days” language/gi, "few comments clearly say they wait more than a month"],
  [/no 30-day delay tag on this theme/gi, "comments don’t clearly say they wait more than a month"],
  [/sale timing/gi, "a sale"],
  [/purchase slips past 30 days/gi, "the buy slips past a month"],
  [/past 30 days/gi, "more than a month"],
  [/increase the share of users who buy at least one wishlisted item/gi, "Help more people buy at least one saved item"],
  [/wishlisted items?/gi, "saved items"],
  [/30-day metric/gi, "buying within a month"],
  [/this metric/gi, "buying within a month"],
  [/the metric/gi, "buying within a month"],
  [/conversion bets?/gi, "reasons people wait"],
  [/opportunity bets?/gi, "topics"],
  [/opportunity areas/gi, "topics"],
  [/near-term purchase intent/gi, "planning to buy soon"],
  [/blocked purchase intent/gi, "wanting to buy but getting stuck"],
  [/purchase intent/gi, "wanting to buy"],
  [/miss the 30-day buy/gi, "don’t get bought within a month"],
  [/within 30 days of save/gi, "within a month of saving"],
  [/within 30 days of adding it/gi, "within a month of saving it"],
  [/within 30 days of adding/gi, "within a month of saving"],
  [/30-day conversion stays low/gi, "buying within a month stays unlikely"],
  [/30-day conversion is unlikely/gi, "buying within a month is unlikely"],
  [/30-day wishlist conversion/gi, "buying from a wishlist within a month"],
  [/30-day conversion/gi, "buying within a month"],
  [/wishlist → purchase in general/gi, "buying a saved item at all"],
  [/wishlist → purchase/gi, "saved item to order"],
  [/blocks_purchase_ever/gi, "stops the buy altogether"],
  [/often stops people from buying a saved item at all/gi, "often stops people from buying a saved item at all"],
  [/often keeps a saved item from becoming an order/gi, "often keeps a saved item from becoming an order"],
  [/kill conversion/gi, "stop the buy"],
  [/can miss a 30-day clock/gi, "can make them wait more than a month"],
  [/often after the 30-day window/gi, "often after a month"],
  [/inside 30 days/gi, "within a month"],
  [/choice paralysis/gi, "too many options"],
  [/shortlisted products/gi, "saved options"],
  [/shortlisted item/gi, "saved item"],
  [/social confidence/gi, "feeling sure about the look"],
  [/bookmarking/gi, "saving for later"],
  [/is used as a bookmark/gi, "is used as a later list"],
  [/items parked from a photo/gi, "items saved from a photo"],
  [/even when intent is high/gi, "even when they want the item"],
  [/little true intent/gi, "little real plan to buy now"],
  [/delivery rants/gi, "delivery complaints"],
  [/weakly tied to wishlist add/gi, "not clearly about saved items"],
  [/postpones the buy/gi, "delays the buy"],
  [/impulse park/gi, "saving on impulse"],
  [/a bookmark/gi, "saving for later"],
  [/\bbookmark\b/gi, "saving for later"],
  [/\bPDP\b/g, "product page"],
  [/\bSKUs?\b/g, "products"],
  [/unfiltered reviews/gi, "all reviews"],
  [/in this corpus/gi, "in the comments we read"],
  [/the text does not yet show/gi, "comments do not yet show"],
  [/that is a job \(why the list exists\), not a star rating\./gi, "That is why they save — not a star rating."],
  [/each factor is a conversion job or blocker, not a sentiment topic\./gi, "Each of these is a reason to save or a reason not to buy yet."],
  [/loud-but-weak themes/gi, "topics people mention a lot but that may not delay buying"],
  [/loud vs this metric/gi, "mentioned often, weaker for buying"],
  [/tied to the metric/gi, "linked to delayed buying"],
  [/composite conversion score/gi, "how likely people are to buy"],
  [/recent 90 days/gi, "the last 3 months"],
  [/volume rank/gi, "how often mentioned"],
  [/conversion rank/gi, "how much it delays buying"],
  [/postponement/gi, "waiting"],
  [/hypothesis/gi, "idea to try"],
  [/grounded quotes/gi, "quotes from shoppers"],
  [/metric_relevance/gi, "how much it makes people wait"],
  [/prevalence_unfiltered/gi, "how often it is mentioned"],
  [/unfiltered share/gi, "how often it is mentioned"],
  [/90-day view/gi, "last 3 months"],
  [/conversion view/gi, "buying within a month"],
  [/higher 30-day delay score/gi, "makes people wait longer after saving"],
  [/lower share waiting past 30 days/gi, "fewer people say they wait more than a month"],
  [/outranks/gi, "matters more than"],
  [/shortlist_compare share/gi, "share of people comparing options"],
  [/intent_blocked job/gi, "want it but stuck"],
  [/bookmark_later job/gi, "saving for later"],
  [/impulse_park job/gi, "saving on impulse"],
  [/wait_for_sale job/gi, "waiting for a sale"],
  [/unknown link to the 30-day/gi, "we don’t yet know how much this delays"],
  [/one of the most common themes in comments about saved items/gi, "one of the most common reasons people mention"],
  [/a noticeable slice of comments about saved items/gi, "a fairly common reason"],
  [/a smaller slice of comments about saved items/gi, "less common, but still shows up"],
  [/share of comments about saved items is unknown/gi, "we don’t yet know how common this is"],
  [/users park saved items/gi, "people keep saved items"],
  [/by design/gi, "on purpose"],
  [/\bbets?\b/gi, "topics"],
];

export function easyCopy(text: string | null | undefined, titles?: Record<string, string>): string {
  if (!text) return "";
  let out = text;
  if (titles) {
    const ids = Object.keys(titles).sort((a, b) => b.length - a.length);
    for (const id of ids) {
      if (!id) continue;
      out = out.split(id).join(titles[id]);
    }
  }
  for (const [pattern, replacement] of PHRASE_SWAPS) {
    out = out.replace(pattern, replacement);
  }
  return out.replace(/\s{2,}/g, " ").trim();
}

export function questionTitle(id: string, fallback: string): string {
  return QUESTION_TITLES[id] || easyCopy(fallback);
}

export function scenarioLabel(scenario: string | undefined): string {
  if (scenario === "general") return "Buy at all";
  if (scenario === "within_30d") return "Within a month";
  if (scenario === "both") return "Both";
  return "";
}

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] || source.replace(/_/g, " ");
}

const JOB_FILTER_LABELS: Record<string, string> = {
  wait_for_sale: "Waiting for a sale",
  bookmark_later: "Saving for later",
  shortlist_compare: "Comparing options",
  intent_blocked: "Want it but stuck",
  occasion_social: "For an occasion",
  impulse_park: "Saved from a photo",
  unknown: "Unclear reason",
};

const BLOCKER_FILTER_LABELS: Record<string, string> = {
  price: "Price",
  sale_timing: "Sale timing",
  fit: "Fit",
  size_chart: "Size chart",
  returns: "Returns",
  photo_mismatch: "Photos vs reality",
  fabric_quality: "Fabric or quality",
  authenticity: "Authenticity",
  competitor_check: "Checking competitors",
  delivery_checkout_saved: "Checkout issue",
  review_volume_trust: "Not enough reviews",
  styling_occasion: "Occasion or styling",
  social_validation: "Social validation",
};

export function filterJobLabel(key: string): string {
  return JOB_FILTER_LABELS[key] || easyCopy(key.replace(/_/g, " "));
}

export function filterBlockerLabel(key: string): string {
  return BLOCKER_FILTER_LABELS[key] || easyCopy(key.replace(/_/g, " "));
}

export function titleMap(opportunities: Opportunity[]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const row of opportunities) {
    map[row.opportunity_id] = easyCopy(row.problem_one_liner);
  }
  return map;
}

export function shortProblem(text: string, max = 42): string {
  const clean = easyCopy(text).replace(/^Users /i, "").replace(/^People /i, "");
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max).trim()}…`;
}

export function phaseLabel(phase: string | undefined): string {
  const labels: Record<string, string> = {
    collect: "Collecting reviews",
    filter: "Keeping useful comments",
    extract: "Reading comments",
    cluster: "Grouping similar comments",
    rank: "Ranking reasons",
    present: "Latest update",
    foundations: "Setup",
  };
  return phase ? labels[phase] || phase : "—";
}
