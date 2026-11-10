"""Bundled fictional demo hotels, used when no source API keys are configured.

Each `data/demo_*.json` file holds one hotel and its sources.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..models import HotelCandidate, SourceResult

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache
def _load() -> dict[str, tuple[HotelCandidate, list[SourceResult]]]:
    hotels = {}
    for path in sorted(DATA_DIR.glob("demo_*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        hotel = HotelCandidate(**raw["hotel"])
        hotels[hotel.id] = (hotel, [SourceResult(**s) for s in raw["sources"]])
    return hotels


def demo_hotels() -> list[HotelCandidate]:
    return [hotel for hotel, _ in _load().values()]


def demo_data(hotel_id: str) -> tuple[HotelCandidate, list[SourceResult]] | None:
    item = _load().get(hotel_id)
    if item is None:
        return None
    hotel, sources = item
    return hotel, [s.model_copy(deep=True) for s in sources]
