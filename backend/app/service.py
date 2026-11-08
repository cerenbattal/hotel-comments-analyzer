"""Builds reports: fetch from every source, analyze, cache."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx

from .analysis import Analyzer, topic_scores
from .config import Settings
from .connectors import GooglePlaces, SourceError, Tripadvisor
from .connectors.demo import demo_hotel, demo_sources
from .models import AskAnswer, HotelCandidate, Lang, Report, Review, SourceResult
from .normalize import overall_score, source_score

log = logging.getLogger(__name__)


class NotFound(LookupError):
    pass


class TTLCache:
    """In-memory cache. Fine for one server process; move to Redis/Postgres later."""

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


class ReportService:
    def __init__(self, settings: Settings, analyzer: Analyzer, http: httpx.AsyncClient):
        self.settings = settings
        self.analyzer = analyzer
        self._google = (
            GooglePlaces(settings.google_places_api_key, http)
            if settings.google_places_api_key
            else None
        )
        self._tripadvisor = (
            Tripadvisor(settings.tripadvisor_api_key, http) if settings.tripadvisor_api_key else None
        )
        self._data_cache = TTLCache(settings.cache_ttl_seconds)
        self._report_cache = TTLCache(settings.cache_ttl_seconds)
        self._locks: dict[tuple, asyncio.Lock] = {}

    @property
    def demo_mode(self) -> bool:
        return self._google is None

    async def search(self, query: str, lang: Lang) -> list[HotelCandidate]:
        if self.demo_mode:
            return [demo_hotel()]
        return await self._google.search(query, lang)

    async def _hotel_data(self, hotel_id: str, lang: Lang) -> HotelData:
        cached = self._data_cache.get((hotel_id, lang))
        if cached:
            return cached

        if hotel_id.startswith("demo:"):
            if hotel_id != demo_hotel().id:
                raise NotFound(hotel_id)
            data = HotelData(hotel=demo_hotel(), sources=demo_sources())
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
        self._data_cache.set((hotel_id, lang), data)
        return data

    async def report(self, hotel_id: str, lang: Lang) -> Report:
        key = (hotel_id, lang)
        # One build per hotel+language at a time; parallel requests wait for it.
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self._report_cache.get(key)
            if cached:
                return cached
            report = await self._build_report(hotel_id, lang)
            self._report_cache.set(key, report)
            return report

    async def _build_report(self, hotel_id: str, lang: Lang) -> Report:
        data = await self._hotel_data(hotel_id, lang)
        scores = [source_score(s) for s in data.sources]
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

    async def ask(self, hotel_id: str, question: str, lang: Lang) -> AskAnswer:
        data = await self._hotel_data(hotel_id, lang)
        if not data.reviews:
            raise NotFound("No reviews to answer from")
        return await self.analyzer.ask(question, data.reviews, lang)
