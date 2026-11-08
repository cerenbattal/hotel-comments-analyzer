"""Google Places API (New): hotel search, rating, count and up to 5 reviews.

Docs: https://developers.google.com/maps/documentation/places/web-service/op-overview
Terms: show Google attribution next to the data; review text may not be stored
long term, so it is only cached in memory for a few hours.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from ..models import HotelCandidate, Review, SourceResult
from .base import SourceError

BASE = "https://places.googleapis.com/v1"


class GooglePlaces:
    name = "google"

    def __init__(self, api_key: str, client: httpx.AsyncClient):
        self._key = api_key
        self._http = client

    def _headers(self, field_mask: str) -> dict[str, str]:
        return {"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": field_mask}

    async def search(self, query: str, lang: str) -> list[HotelCandidate]:
        resp = await self._http.post(
            f"{BASE}/places:searchText",
            headers=self._headers(
                "places.id,places.displayName,places.formattedAddress,"
                "places.rating,places.userRatingCount"
            ),
            json={"textQuery": query, "includedType": "lodging", "languageCode": lang},
        )
        if resp.status_code != 200:
            raise SourceError(f"Google search failed: HTTP {resp.status_code}")
        return [
            HotelCandidate(
                id=p["id"],
                name=p.get("displayName", {}).get("text", ""),
                address=p.get("formattedAddress"),
                rating=p.get("rating"),
                review_count=p.get("userRatingCount"),
            )
            for p in resp.json().get("places", [])
        ]

    async def details(self, place_id: str, lang: str) -> tuple[HotelCandidate, SourceResult]:
        resp = await self._http.get(
            f"{BASE}/places/{place_id}",
            params={"languageCode": lang},
            headers=self._headers(
                "id,displayName,formattedAddress,rating,userRatingCount,reviews,googleMapsUri"
            ),
        )
        if resp.status_code == 404:
            raise SourceError("Hotel not found on Google")
        if resp.status_code != 200:
            raise SourceError(f"Google details failed: HTTP {resp.status_code}")
        p = resp.json()
        hotel = HotelCandidate(
            id=p["id"],
            name=p.get("displayName", {}).get("text", ""),
            address=p.get("formattedAddress"),
            rating=p.get("rating"),
            review_count=p.get("userRatingCount"),
        )
        reviews = []
        for i, r in enumerate(p.get("reviews", [])):
            # originalText keeps the guest's own language; text may be translated.
            body = r.get("originalText") or r.get("text") or {}
            if not body.get("text"):
                continue
            reviews.append(
                Review(
                    id=f"google:{i}",
                    source=self.name,
                    rating=r.get("rating"),
                    scale_max=5,
                    text=body["text"],
                    language=body.get("languageCode"),
                    author=(r.get("authorAttribution") or {}).get("displayName"),
                    published=_parse_date(r.get("publishTime")),
                    url=r.get("googleMapsUri"),
                )
            )
        result = SourceResult(
            source=self.name,
            source_label="Google Maps",
            external_id=hotel.id,
            rating=p.get("rating"),
            scale_max=5,
            review_count=p.get("userRatingCount") or 0,
            url=p.get("googleMapsUri"),
            attribution="Google",
            reviews=reviews,
        )
        return hotel, result


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
