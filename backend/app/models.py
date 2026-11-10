"""Shared data models for the API and the analysis pipeline."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Lang = Literal["tr", "en", "de", "fr", "es", "ru", "ar"]

Topic = Literal[
    "cleanliness",
    "staff",
    "location",
    "room",
    "breakfast",
    "food",
    "noise",
    "wifi",
    "value",
    "facilities",
]

TOPICS: tuple[str, ...] = Topic.__args__  # type: ignore[attr-defined]


class Review(BaseModel):
    id: str
    source: str
    rating: float | None = None  # in the source's own scale
    scale_max: float = 5
    text: str
    language: str | None = None
    author: str | None = None
    published: date | None = None
    url: str | None = None


class SourceResult(BaseModel):
    """What one source knows about the hotel."""

    source: str
    source_label: str
    external_id: str
    rating: float | None  # in the source's own scale
    scale_max: float
    review_count: int
    url: str | None = None
    attribution: str | None = None
    reviews: list[Review] = Field(default_factory=list)


class HotelCandidate(BaseModel):
    id: str  # Google place id, or "demo:<slug>"
    name: str
    address: str | None = None
    rating: float | None = None
    review_count: int | None = None


class SourceScore(BaseModel):
    source: str
    source_label: str
    rating: float | None
    scale_max: float
    score_10: float | None
    review_count: int
    url: str | None = None
    attribution: str | None = None


class TopicScore(BaseModel):
    topic: Topic
    score_10: float
    positive: int
    negative: int


class Point(BaseModel):
    """One pro or con, with how often it comes up and quotes as evidence."""

    text: str
    mentions: int
    quotes: list[str] = Field(default_factory=list)


FlagCode = Literal[
    "source_gap",  # one source scores the hotel far above the others
    "five_star_burst",  # many 5-star reviews within a few days
    "duplicate_text",  # near-identical texts under different reviews
    "rating_text_mismatch",  # e.g. 5 stars on a text that only complains
    "short_five_star",  # many very short 5-star reviews
]


class TrustFlag(BaseModel):
    code: FlagCode
    # Values the frontend puts into its translated sentence for this code.
    source: str | None = None
    gap: float | None = None
    count: int | None = None
    total: int | None = None
    days: int | None = None


class Trust(BaseModel):
    level: Literal["ok", "caution"] = "ok"
    flags: list[TrustFlag] = Field(default_factory=list)


class Report(BaseModel):
    hotel_id: str
    hotel_name: str
    address: str | None = None
    lang: Lang
    overall_score_10: float | None
    total_reviews: int
    analyzed_reviews: int
    sources: list[SourceScore]
    topics: list[TopicScore]
    pros: list[Point]
    cons: list[Point]
    summary: str
    # Reports stored before trust signals existed have none.
    trust: Trust = Field(default_factory=Trust)


class ReportJob(BaseModel):
    """State of a report build. The frontend polls this until it is done or failed."""

    status: Literal["running", "done", "failed"]
    report: Report | None = None
    error: str | None = None


class HistoryPoint(BaseModel):
    source: str
    day: date
    score_10: float | None
    review_count: int


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    lang: Lang = "en"


class AskAnswer(BaseModel):
    answer: str
    quotes: list[str] = Field(default_factory=list)
