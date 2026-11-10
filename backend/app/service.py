"""Builds reports: fetch from every source, analyze, store.

A report takes 20-40 seconds (several Claude calls), so it is built in a
background task. The API starts the build and the frontend polls its status.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from .analysis import AnalysisError, Analyzer, topic_scores
from .config import Settings
from .connectors import GooglePlaces, SourceError, Tripadvisor
from .connectors.demo import demo_data, demo_hotels
from .db import ReportRow, ScoreSnapshot, utcnow
from .models import (
    AskAnswer,
    HistoryPoint,
    HotelCandidate,
    Lang,
    Report,
    ReportJob,
    Review,
    SourceResult,
    SourceScore,
)
from .normalize import overall_score, source_score

log = logging.getLogger(__name__)

# A build still "running" after this long is assumed lost (e.g. server restart).
STALE_BUILD = timedelta(minutes=10)


class NotFound(LookupError):
    pass


class TTLCache:
    """In-memory cache for fetched reviews (kept out of the database on purpose)."""

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._items: dict[tuple, tuple[float, object]] = {}

    def get(self, key: tuple):
        item = self._items.get(key)
        if not item or item[0] < time.monotonic():
            self._items.pop(key, None)
            return None
        return item[1]

    def set(self, key: tuple, value) -> None:
        self._items[key] = (time.monotonic() + self._ttl, value)


@dataclass
class HotelData:
    hotel: HotelCandidate
    sources: list[SourceResult]
    reviews: list[Review] = field(default_factory=list)


def dedupe(reviews: list[Review]) -> list[Review]:
    seen: set[str] = set()
    out = []
    for r in reviews:
        key = " ".join(r.text.lower().split())
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _job(row: ReportRow) -> ReportJob:
    return ReportJob(
        status=row.status,
        report=Report(**row.report) if row.report else None,
        error=row.error,
    )


class ReportService:
    def __init__(
        self,
        settings: Settings,
        analyzer: Analyzer,
        http: httpx.AsyncClient,
        sessions: async_sessionmaker,
    ):
        self.settings = settings
        self.analyzer = analyzer
        self.sessions = sessions
        self._google = (
            GooglePlaces(settings.google_places_api_key, http)
            if settings.google_places_api_key
            else None
        )
        self._tripadvisor = (
            Tripadvisor(settings.tripadvisor_api_key, http) if settings.tripadvisor_api_key else None
        )
        self._data_cache = TTLCache(settings.cache_ttl_seconds)
        self._start_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()

    @property
    def demo_mode(self) -> bool:
        return self._google is None

    async def search(self, query: str, lang: Lang) -> list[HotelCandidate]:
        if self.demo_mode:
            return demo_hotels()
        return await self._google.search(query, lang)

    # ---------- fetching ----------

    async def _hotel_data(self, hotel_id: str, lang: Lang) -> HotelData:
        cached = self._data_cache.get((hotel_id, lang))
        if cached:
            return cached
        data = await self._fetch(hotel_id, lang)
        self._data_cache.set((hotel_id, lang), data)
        return data

    async def _fetch(self, hotel_id: str, lang: Lang) -> HotelData:
        """Fetch a hotel from every source, without the cache."""
        if hotel_id.startswith("demo:"):
            demo = demo_data(hotel_id)
            if demo is None:
                raise NotFound(hotel_id)
            data = HotelData(hotel=demo[0], sources=demo[1])
        else:
            if self._google is None:
                raise NotFound(hotel_id)
            try:
                hotel, google_result = await self._google.details(hotel_id, lang)
            except SourceError as e:
                raise NotFound(str(e)) from e
            sources = [google_result]
            if self._tripadvisor:
                try:
                    ta = await self._tripadvisor.fetch(hotel, lang)
                    if ta:
                        sources.append(ta)
                except (SourceError, httpx.HTTPError) as e:
                    # One source failing should not break the report.
                    log.warning("Tripadvisor skipped for %s: %s", hotel_id, e)
            data = HotelData(hotel=hotel, sources=sources)

        data.reviews = dedupe([r for s in data.sources for r in s.reviews])
        return data

    # ---------- report jobs ----------

    async def _latest(self, session, hotel_id: str, lang: Lang) -> ReportRow | None:
        return await session.scalar(
            select(ReportRow)
            .where(ReportRow.hotel_id == hotel_id, ReportRow.lang == lang)
            .order_by(ReportRow.id.desc())
            .limit(1)
        )

    async def get_report(self, hotel_id: str, lang: Lang) -> ReportJob | None:
        async with self.sessions() as session:
            row = await self._latest(session, hotel_id, lang)
            return _job(row) if row else None

    async def start_report(self, hotel_id: str, lang: Lang) -> ReportJob:
        """Return a fresh finished report, the build in progress, or start a new build."""
        async with self._start_lock, self.sessions() as session:
            row = await self._latest(session, hotel_id, lang)
            now = utcnow()
            if row and row.status == "done" and row.finished_at and (
                now - _aware(row.finished_at) < timedelta(seconds=self.settings.cache_ttl_seconds)
            ):
                return _job(row)
            if row and row.status == "running" and now - _aware(row.created_at) < STALE_BUILD:
                return _job(row)

            row = ReportRow(hotel_id=hotel_id, lang=lang, status="running")
            session.add(row)
            await session.commit()
            task = asyncio.create_task(self._run_build(row.id, hotel_id, lang))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            return _job(row)

    async def wait_for_builds(self) -> None:
        """Used by tests and on shutdown."""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _run_build(self, row_id: int, hotel_id: str, lang: Lang) -> None:
        try:
            report = await self._build_report(hotel_id, lang)
            status, error, payload = "done", None, report.model_dump(mode="json")
        except NotFound:
            status, error, payload = "failed", "Hotel not found", None
        except AnalysisError as e:
            status, error, payload = "failed", str(e), None
        except Exception:
            log.exception("Report build failed for %s", hotel_id)
            status, error, payload = "failed", "Unexpected error while building the report", None
        async with self.sessions() as session:
            row = await session.get(ReportRow, row_id)
            row.status, row.error, row.report, row.finished_at = status, error, payload, utcnow()
            await session.commit()

    async def _build_report(self, hotel_id: str, lang: Lang) -> Report:
        data = await self._hotel_data(hotel_id, lang)
        scores = [source_score(s) for s in data.sources]
        await self._record_scores(data.hotel.id, scores)
        insights = await self.analyzer.extract(data.reviews) if data.reviews else []
        if data.reviews:
            summary = await self.analyzer.summarize(data.hotel.name, data.reviews, insights, lang)
            pros, cons, text = summary.pros, summary.cons, summary.summary
        else:
            pros, cons, text = [], [], ""
        return Report(
            hotel_id=data.hotel.id,
            hotel_name=data.hotel.name,
            address=data.hotel.address,
            lang=lang,
            overall_score_10=overall_score(scores),
            total_reviews=sum(s.review_count for s in scores),
            analyzed_reviews=len(insights),
            sources=scores,
            topics=topic_scores(insights),
            pros=pros,
            cons=cons,
            summary=text,
        )

    # ---------- score history ----------

    async def _record_scores(
        self, hotel_id: str, scores: list[SourceScore], day: date | None = None
    ) -> None:
        """Keep one snapshot per source per day; a later fetch the same day replaces it."""
        day = day or utcnow().date()
        async with self.sessions() as session:
            for s in scores:
                row = await session.scalar(
                    select(ScoreSnapshot).where(
                        ScoreSnapshot.hotel_id == hotel_id,
                        ScoreSnapshot.source == s.source,
                        ScoreSnapshot.day == day,
                    )
                )
                if row is None:
                    row = ScoreSnapshot(hotel_id=hotel_id, source=s.source, day=day)
                    session.add(row)
                row.rating, row.scale_max = s.rating, s.scale_max
                row.score_10, row.review_count = s.score_10, s.review_count
            await session.commit()

    async def refresh_scores(self, active_days: int = 30) -> int:
        """Save today's score for every real hotel someone opened in the last `active_days`.

        Only the sources' ratings are fetched (no Claude calls), so this is cheap.
        Returns how many hotels were refreshed.
        """
        since = utcnow() - timedelta(days=active_days)
        async with self.sessions() as session:
            hotel_ids = list(
                await session.scalars(
                    select(ReportRow.hotel_id).where(ReportRow.created_at >= since).distinct()
                )
            )
        refreshed = 0
        for hotel_id in hotel_ids:
            if hotel_id.startswith("demo:"):
                continue  # demo scores never change
            try:
                data = await self._fetch(hotel_id, "en")
                await self._record_scores(data.hotel.id, [source_score(s) for s in data.sources])
                refreshed += 1
            except Exception as e:  # one hotel failing must not stop the others
                log.warning("Score refresh failed for %s: %s", hotel_id, e)
        log.info("Daily score refresh: %d of %d hotels", refreshed, len(hotel_ids))
        return refreshed

    async def history(self, hotel_id: str) -> list[HistoryPoint]:
        async with self.sessions() as session:
            rows = await session.scalars(
                select(ScoreSnapshot)
                .where(ScoreSnapshot.hotel_id == hotel_id)
                .order_by(ScoreSnapshot.day, ScoreSnapshot.source)
            )
            return [
                HistoryPoint(
                    source=r.source, day=r.day, score_10=r.score_10, review_count=r.review_count
                )
                for r in rows
            ]

    # ---------- ask ----------

    async def ask(self, hotel_id: str, question: str, lang: Lang) -> AskAnswer:
        data = await self._hotel_data(hotel_id, lang)
        if not data.reviews:
            raise NotFound("No reviews to answer from")
        return await self.analyzer.ask(question, data.reviews, lang)
