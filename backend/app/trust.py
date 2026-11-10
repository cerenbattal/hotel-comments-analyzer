"""Signals that some reviews may not be genuine.

These are heuristics, not proof: each flag says "worth a closer look". Thresholds
are deliberately conservative because the MVP sees only ~5 reviews per source,
and a false alarm on an honest hotel is worse than a missed one.
"""

from __future__ import annotations

import re
from datetime import timedelta
from statistics import median

from .analysis import ReviewInsight
from .models import Review, SourceScore, Trust, TrustFlag

SOURCE_GAP = 1.5  # points on the 0-10 scale
BURST_DAYS = 3
MIN_REVIEWS = 5
DUPLICATE_SIMILARITY = 0.6
SHORT_WORDS = 6


def _is_five_star(r: Review) -> bool:
    return r.rating is not None and r.rating >= r.scale_max


def _shingles(text: str, n: int = 3) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def source_gap(scores: list[SourceScore]) -> list[TrustFlag]:
    flags = []
    scored = [s for s in scores if s.score_10 is not None and s.review_count > 0]
    if len(scored) < 2:
        return flags
    for s in scored:
        others = [o.score_10 for o in scored if o is not s]
        gap = s.score_10 - median(others)
        if gap >= SOURCE_GAP:
            flags.append(TrustFlag(code="source_gap", source=s.source_label, gap=round(gap, 1)))
    return flags


def five_star_burst(reviews: list[Review], labels: dict[str, str] | None = None) -> list[TrustFlag]:
    """At least half of a source's dated reviews are 5 stars within BURST_DAYS days."""
    flags = []
    for source in sorted({r.source for r in reviews}):
        dated = [r for r in reviews if r.source == source and r.published]
        if len(dated) < MIN_REVIEWS:
            continue
        fives = sorted(r.published for r in dated if _is_five_star(r))
        best = 0
        for i, start in enumerate(fives):
            best = max(best, sum(1 for d in fives[i:] if d - start <= timedelta(days=BURST_DAYS)))
        if best >= 3 and best * 2 >= len(dated):
            flags.append(
                TrustFlag(
                    code="five_star_burst",
                    source=(labels or {}).get(source, source),
                    count=best,
                    total=len(dated),
                    days=BURST_DAYS,
                )
            )
    return flags


def duplicate_text(reviews: list[Review]) -> list[TrustFlag]:
    """Pairs of reviews whose word 3-grams overlap heavily (Jaccard similarity)."""
    sets = [(r, _shingles(r.text)) for r in reviews]
    dupes: set[str] = set()
    for i, (a, sa) in enumerate(sets):
        for b, sb in sets[i + 1 :]:
            if len(sa) < 4 or len(sb) < 4:
                continue  # too short to judge
            if len(sa & sb) / len(sa | sb) >= DUPLICATE_SIMILARITY:
                dupes.update((a.id, b.id))
    return [TrustFlag(code="duplicate_text", count=len(dupes), total=len(reviews))] if dupes else []


def rating_text_mismatch(reviews: list[Review], insights: list[ReviewInsight]) -> list[TrustFlag]:
    """Top rating on a text that only complains, or bottom rating on one that only praises."""
    by_id = {i.review_id: i for i in insights}
    count = 0
    for r in reviews:
        ins = by_id.get(r.id)
        if r.rating is None or ins is None:
            continue
        pos = sum(1 for m in ins.topics if m.sentiment == "positive")
        neg = sum(1 for m in ins.topics if m.sentiment == "negative")
        share = (r.rating - 1) / (r.scale_max - 1) if r.scale_max > 1 else 0
        if (share >= 0.875 and neg >= 2 and pos == 0) or (share <= 0.25 and pos >= 2 and neg == 0):
            count += 1
    return [TrustFlag(code="rating_text_mismatch", count=count, total=len(reviews))] if count else []


def short_five_star(reviews: list[Review]) -> list[TrustFlag]:
    if len(reviews) < MIN_REVIEWS:
        return []
    short = [r for r in reviews if _is_five_star(r) and len(r.text.split()) < SHORT_WORDS]
    if len(short) >= 3 and len(short) * 3 >= len(reviews):
        return [TrustFlag(code="short_five_star", count=len(short), total=len(reviews))]
    return []


def assess(scores: list[SourceScore], reviews: list[Review], insights: list[ReviewInsight]) -> Trust:
    flags = [
        *source_gap(scores),
        *five_star_burst(reviews, {s.source: s.source_label for s in scores}),
        *duplicate_text(reviews),
        *rating_text_mismatch(reviews, insights),
        *short_five_star(reviews),
    ]
    return Trust(level="caution" if flags else "ok", flags=flags)
