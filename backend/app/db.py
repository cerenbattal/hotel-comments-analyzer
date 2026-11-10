"""Database: finished reports and a daily history of each source's score.

Only numbers (ratings, counts) and our own analysis are stored. Raw review text
is not stored, because Google's terms limit how long review content may be kept.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ReportRow(Base):
    """One report build for a hotel in one language. The newest row wins."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[str] = mapped_column(String(300), index=True)
    lang: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(10))  # running | done | failed
    error: Mapped[str | None] = mapped_column(Text)
    report: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScoreSnapshot(Base):
    """A source's rating for a hotel on one day; feeds the score-over-time chart."""

    __tablename__ = "score_snapshots"
    __table_args__ = (UniqueConstraint("hotel_id", "source", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[str] = mapped_column(String(300), index=True)
    source: Mapped[str] = mapped_column(String(40))
    day: Mapped[date] = mapped_column(Date)
    rating: Mapped[float | None] = mapped_column(Float)
    scale_max: Mapped[float] = mapped_column(Float)
    score_10: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int] = mapped_column(Integer)


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    # Fine while the schema is small; switch to Alembic migrations before the
    # first schema change in production.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
