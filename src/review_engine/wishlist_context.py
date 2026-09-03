"""Signals that tie blockers to saved-item save or purchase delay."""

from __future__ import annotations

import re

_SAVED_OR_DELAY = re.compile(
    r"wish\s*list|wishlisted|saved for later|save[d]?\s+for|bookmark|shortlist|\bi saved\b|"
    r"saved (?:this|it|that|the|item|product|dress|kurta|shirt|shoes|pair)\b|"
    r"won'?t buy|will not buy|not (?:buying|ordering) yet|before (?:i )?(?:buy|order)|"
    r"hesitat.{0,40}(?:buy|order)|afraid to (?:buy|order)",
    re.I,
)

_COMPARE_CONTEXT = re.compile(
    r"confused between|shortlist(?:ed|ing)?|myntra or ajio|between these two|"
    r"compar(?:e|ing).{0,30}(?:product|item|option|dress|shoes|pair)",
    re.I,
)

_WISHLIST_EXPLICIT = re.compile(
    r"wish\s*list|wishlisted|saved for later|bookmark|shortlist|\bi saved\b|"
    r"saved (?:this|it|that|the|item|product)\b|save[d]?\s+for",
    re.I,
)

_OFF_TOPIC_DELIVERY = re.compile(
    r"\bdeliver(?:y|ed|ing)?\b|\bcourier\b|threshold.{0,20}deliv",
    re.I,
)

_RETURN_FEAR = re.compile(
    r"return policy|easy return|no[- ]?hassle return|"
    r"return.{0,30}(?:risky|risk|worr|scar|afraid)|"
    r"(?:worr|scar|afraid).{0,30}return|trust.{0,30}return",
    re.I,
)

_RETURN_WORD = re.compile(r"\breturn", re.I)

_POST_PURCHASE_RETURN = re.compile(
    r"returned (?:it|the|my|product|item)|after return|return kar|refund|money back|"
    r"return pickup|pickup (?:failed|cancel)|exchange (?:only|option)|replaced the product|"
    r"return process|returned in \w+|\bdid not (?:get|receive) (?:my )?refund",
    re.I,
)

_PURCHASE_INTENT = re.compile(
    r"\b(?:love|like|want|buy|order|kurta|dress|shirt|shoes|product|item)\b",
    re.I,
)

_AUTHENTICITY = re.compile(r"\bfake\b|authenticit|replica", re.I)

_FIT_SIZE_TOPIC = re.compile(
    r"size chart|\bsize\b|\bfit\b|too (?:small|big|tight|loose)|wrong size",
    re.I,
)

_POSITIVE_REVIEW = re.compile(
    r"(?:perfect|good|great|nice|wonderful|excellent|amazing|lovely|well|fantastic)\s+"
    r"(?:fit(?:ted)?|size|quality|fabric)|"
    r"(?:fit|quality|fabric).{0,15}(?:perfect|good|great|nice|wonderful|excellent|amazing|lovely|fantastic)|"
    r"glorious look|reasonable for the price|no doubt|purely quality|recommend",
    re.I,
)

_POSITIVE_QUALITY_PRAISE = re.compile(
    r"don'?t hesitate|no doubt|purely quality|fantastic|recommend",
    re.I,
)

_POST_PURCHASE_FIT = re.compile(
    r"wrong size|sent (?:the )?wrong size|size (?:was )?(?:too )?(?:small|big|tight|loose)|"
    r"exchange.{0,30}size|replaced.{0,30}(?:size|product)|damaged|"
    r"did not (?:get|receive)|refund|return",
    re.I,
)

_SIZE_HESITATION = re.compile(
    r"size chart.{0,50}(?:unclear|useless|confus|wrong)|"
    r"(?:unclear|useless|confus).{0,50}size chart|"
    r"won't buy until.{0,40}size|will not buy until.{0,40}size|"
    r"don't know (?:my )?size|not (?:sure|ordered).{0,40}size|"
    r"haven't ordered.{0,40}size|size (?:nahi|nahin) (pata|malum)|"
    r"not sure (?:about )?(?:the )?size|before (?:i )?(?:buy|order).{0,40}size",
    re.I,
)

_FIT_HESITATION = re.compile(
    r"not sure (?:about )?(?:the )?fit|fit (?:is )?(?:uncertain|unclear)|"
    r"won't buy until.{0,40}fit|hesitat.{0,40}fit",
    re.I,
)

_FABRIC_SIGNAL = re.compile(r"\bfabric\b|\bquality\b|thin material", re.I)

_FABRIC_HESITATION = re.compile(
    r"(?:not sure|uncertain|worri|doubt).{0,40}(?:quality|fabric)|"
    r"(?:quality|fabric).{0,40}(?:worri|uncertain|not sure|doubt|before (?:buy|order))",
    re.I,
)

_LOVE_BUT = re.compile(
    r"(?:love|like|want).{0,40}but.{0,40}(?:size|fit|size chart|quality|fabric|return|fake)",
    re.I,
)


def _has_saved_or_compare_context(text: str) -> bool:
    return bool(_SAVED_OR_DELAY.search(text) or _COMPARE_CONTEXT.search(text))


_SALE_SAVE_CONTEXT = re.compile(
    r"(?:wish\s*list|wishlisted|saved(?:\s+for\s+later)?|bookmark|shortlist).{0,100}"
    r"(?:eors|sale|price drop|wait(?:ing)? for (?:the )?sale)|"
    r"(?:eors|wait(?:ing)? for (?:the )?sale|price drop).{0,100}"
    r"(?:wish\s*list|wishlisted|saved(?:\s+for\s+later)?|bookmark|shortlist)",
    re.I,
)


def quote_has_saved_item_context(text: str) -> bool:
    """True when quote text clearly refers to saved items, wishlist, or shortlist."""
    body = (text or "").strip()
    if not body:
        return False
    has_explicit = bool(_WISHLIST_EXPLICIT.search(body) or _SALE_SAVE_CONTEXT.search(body))
    has_compare = bool(_COMPARE_CONTEXT.search(body))
    if not has_explicit and not has_compare:
        return False
    if _OFF_TOPIC_DELIVERY.search(body) and not _WISHLIST_EXPLICIT.search(body):
        return False
    return True


def _has_prebuy_fit_block(text: str) -> bool:
    return bool(_SIZE_HESITATION.search(text) or _FIT_HESITATION.search(text) or _LOVE_BUT.search(text))


def returns_blocks_saved_purchase(text: str) -> bool:
    """True when returns are cited as a reason to hesitate on a saved or not-yet-bought item."""
    body = (text or "").strip()
    if not body or not (_RETURN_WORD.search(body) or _RETURN_FEAR.search(body)):
        return False
    if _POST_PURCHASE_RETURN.search(body) and not _SAVED_OR_DELAY.search(body):
        return False
    if _SAVED_OR_DELAY.search(body):
        return True
    if _RETURN_FEAR.search(body) and _PURCHASE_INTENT.search(body):
        return True
    return False


def authenticity_blocks_saved_purchase(text: str) -> bool:
    body = (text or "").strip()
    if not body or not _AUTHENTICITY.search(body):
        return False
    if _POST_PURCHASE_RETURN.search(body) and not _SAVED_OR_DELAY.search(body):
        return False
    if _SAVED_OR_DELAY.search(body):
        return True
    return bool(_LOVE_BUT.search(body))


def fit_blocks_saved_purchase(text: str) -> bool:
    """True when size/fit uncertainty blocks buying or saving with intent."""
    body = (text or "").strip()
    if not body or not _FIT_SIZE_TOPIC.search(body):
        return False
    if _POSITIVE_REVIEW.search(body) and not _has_prebuy_fit_block(body):
        return False
    if (
        _POST_PURCHASE_FIT.search(body)
        and not _has_saved_or_compare_context(body)
        and not _has_prebuy_fit_block(body)
    ):
        return False
    if _has_prebuy_fit_block(body):
        return True
    if _has_saved_or_compare_context(body) and (
        _SIZE_HESITATION.search(body) or _FIT_HESITATION.search(body)
    ):
        return True
    return False


def size_chart_blocks_saved_purchase(text: str) -> bool:
    body = (text or "").strip()
    return bool(re.search(r"size chart", body, re.I)) and fit_blocks_saved_purchase(body)


def fabric_quality_blocks_saved_purchase(text: str) -> bool:
    """True when fabric/quality doubt blocks buying a saved or not-yet-bought item."""
    body = (text or "").strip()
    if not body or not _FABRIC_SIGNAL.search(body):
        return False
    if _POSITIVE_QUALITY_PRAISE.search(body):
        return False
    if _POSITIVE_REVIEW.search(body) and not _FABRIC_HESITATION.search(body) and not _LOVE_BUT.search(body):
        return False
    if (
        _POST_PURCHASE_FIT.search(body)
        and not _has_saved_or_compare_context(body)
        and not _FABRIC_HESITATION.search(body)
    ):
        return False
    if _FABRIC_HESITATION.search(body):
        return _has_saved_or_compare_context(body) or bool(
            re.search(r"won't buy|will not buy|before (?:i )?(?:buy|order)", body, re.I)
        )
    if _LOVE_BUT.search(body) and _FABRIC_SIGNAL.search(body):
        return True
    return False


def fit_uncertainty_signal(text: str) -> bool:
    return fit_blocks_saved_purchase(text) or fabric_quality_blocks_saved_purchase(text)


def returns_trust_signal(text: str) -> bool:
    return returns_blocks_saved_purchase(text) or authenticity_blocks_saved_purchase(text)
