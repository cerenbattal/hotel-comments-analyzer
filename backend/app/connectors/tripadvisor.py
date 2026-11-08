"""Tripadvisor Content API: rating, count and up to 5 reviews per hotel.

Docs: https://tripadvisor-content-api.readme.io/
Terms: Tripadvisor attribution (logo + link) must be shown next to the data.
"""

from __future__ import annotations

from datetime import date

import httpx

from ..models import HotelCandidate, Review, SourceResult
from .base import SourceError

BASE = "https://api.content.tripadvisor.com/api/v1"


class Tripadvisor:
    name = "tripadvisor"

    def __init__(self, api_key: str, client: httpx.AsyncClient):
        self._key = api_key
        self._http = client

    async def _get(self, path: str, **params) -> dict:
        resp = await self._http.get(
            f"{BASE}{path}",
            params={"key": self._key, **params},
            headers={"accept": "application/json"},
        )
        if resp.status_code != 200:
            raise SourceError(f"Tripadvisor {path} failed: HTTP {resp.status_code}")
        return resp.json()

    async def _match(self, hotel: HotelCandidate, lang: str) -> str | None:
        query = hotel.name if not hotel.address else f"{hotel.name} {hotel.address}"
        data = await self._get(
            "/location/search", searchQuery=query[:120], category="hotels", language=lang
        )
        results = data.get("data", [])
        if not results and hotel.address:
            data = await self._get(
                "/location/search", searchQuery=hotel.name, category="hotels", language=lang
            )
            results = data.get("data", [])
        return results[0]["location_id"] if results else None

    async def fetch(self, hotel: HotelCandidate, lang: str) -> SourceResult | None:
        location_id = await self._match(hotel, lang)
        if not location_id:
            return None
        details = await self._get(f"/location/{location_id}/details", language=lang)
        reviews_data = await self._get(f"/location/{location_id}/reviews", language=lang)
        reviews = [
            Review(
                id=f"tripadvisor:{r.get('id', i)}",
                source=self.name,
                rating=r.get("rating"),
                scale_max=5,
                text=" ".join(x for x in (r.get("title"), r.get("text")) if x),
                language=r.get("lang"),
                author=(r.get("user") or {}).get("username"),
                published=_parse_date(r.get("published_date")),
                url=r.get("url"),
            )
            for i, r in enumerate(reviews_data.get("data", []))
            if r.get("text")
        ]
        return SourceResult(
            source=self.name,
            source_label="Tripadvisor",
            external_id=str(location_id),
            rating=_to_float(details.get("rating")),
            scale_max=5,
            review_count=int(_to_float(details.get("num_reviews")) or 0),
            url=details.get("web_url"),
            attribution="Tripadvisor",
            reviews=reviews,
        )


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
