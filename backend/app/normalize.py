"""Score normalization: every source's scale to 0-10, then one weighted overall score."""

from __future__ import annotations

import math

from .models import SourceResult, SourceScore


def to_ten(rating: float | None, scale_max: float, scale_min: float = 1) -> float | None:
    """Map a rating to 0-10.

    Most review scales start at 1 (Google, Tripadvisor 1-5; Booking 1-10), so a
    linear map from [min, max] to [0, 10] keeps "worst possible" at 0 instead of
    pretending a 1/5 is a 2/10.
    """
    if rating is None:
        return None
    if scale_max <= scale_min:
        raise ValueError("scale_max must be greater than scale_min")
    clamped = min(max(rating, scale_min), scale_max)
    return round((clamped - scale_min) / (scale_max - scale_min) * 10, 2)


def source_score(result: SourceResult) -> SourceScore:
    return SourceScore(
        source=result.source,
        source_label=result.source_label,
        rating=result.rating,
        scale_max=result.scale_max,
        score_10=to_ten(result.rating, result.scale_max),
        review_count=result.review_count,
        url=result.url,
        attribution=result.attribution,
    )


def overall_score(scores: list[SourceScore]) -> float | None:
    """Weighted average of per-source 0-10 scores.

    Weight grows with the log of the review count, so 2,000 reviews count more
    than 12, but one giant source cannot drown out everyone else.
    """
    weighted = [
        (s.score_10, math.log10(s.review_count + 1))
        for s in scores
        if s.score_10 is not None and s.review_count > 0
    ]
    total_weight = sum(w for _, w in weighted)
    if not weighted or total_weight == 0:
        return None
    return round(sum(score * w for score, w in weighted) / total_weight, 1)
