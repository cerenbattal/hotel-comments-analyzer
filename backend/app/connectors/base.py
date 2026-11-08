from __future__ import annotations

from typing import Protocol

from ..models import HotelCandidate, SourceResult


class SourceError(RuntimeError):
    """A source could not be reached or returned an unusable answer."""


class SearchSource(Protocol):
    async def search(self, query: str, lang: str) -> list[HotelCandidate]: ...


class ReviewSource(Protocol):
    """One review platform. Add a new platform by implementing this."""

    name: str

    async def fetch(self, hotel: HotelCandidate, lang: str) -> SourceResult | None:
        """Return the hotel's score and reviews on this source, or None if not found."""
        ...
