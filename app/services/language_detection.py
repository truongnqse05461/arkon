"""Language detection — thin wrapper around langid for the MRP pipeline.

Returns ISO 639-1 codes ("en", "zh", "vi", ...) and a normalized 0-1 confidence.
Callers compare confidence against settings.language_detection_min_confidence
and treat low-confidence results as "unknown" (skip translation).
"""

import math
from typing import Tuple

import langid

_SAMPLE_CHARS = 2000
# Divisor for sigmoid normalization of the log-likelihood margin between the
# top-ranked language and the runner-up.  Tuned so that a margin of ~50 nats
# (typical for a clear Chinese match) yields conf ≈ 0.62 and a margin of ~100
# nats (typical English) yields conf ≈ 0.74.  Vietnamese diacritics produce
# margins >900, giving conf → 1.0.
_MARGIN_DIVISOR = 100.0


def detect_language(text: str) -> Tuple[str, float]:
    """Detect language of `text`. Uses up to the first 2000 characters.

    Returns:
        (iso_code, confidence) where confidence is a 0-1 normalized score.
        Confidence is derived from the log-likelihood margin between the
        top-ranked language and its runner-up: a larger margin means langid is
        more certain, mapped through a sigmoid so the result stays in [0, 1].
    """
    if not text or not text.strip():
        return ("en", 0.0)

    sample = text[:_SAMPLE_CHARS]
    ranked = langid.rank(sample)
    if not ranked:
        return ("en", 0.0)

    top_code, top_score = ranked[0]
    if len(ranked) < 2:
        return (top_code, 1.0)

    second_score = ranked[1][1]
    # Both scores are log-likelihoods (negative); top_score is the most
    # negative (highest likelihood).  The absolute margin measures separation.
    abs_margin = abs(top_score - second_score)
    confidence = 1.0 / (1.0 + math.exp(-abs_margin / _MARGIN_DIVISOR))
    return (top_code, confidence)
