"""Bundled fictional demo hotel, used when no source API keys are configured."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..models import HotelCandidate, SourceResult

DATA = Path(__file__).resolve().parent.parent / "data" / "demo_hotel.json"


@lru_cache
def _load() -> tuple[HotelCandidate, list[SourceResult]]:
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    return HotelCandidate(**raw["hotel"]), [SourceResult(**s) for s in raw["sources"]]


def demo_hotel() -> HotelCandidate:
    return _load()[0]


def demo_sources() -> list[SourceResult]:
    return [s.model_copy(deep=True) for s in _load()[1]]
