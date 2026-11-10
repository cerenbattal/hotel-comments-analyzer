"""In-memory request limits that keep a public deployment's API bills bounded.

Each limit is a sliding window per key (a client IP, or "*" for the global daily
caps). Counts live in this process only, so with several API replicas each one
enforces its own share; move the counters to Redis if that ever matters.
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Callable

from .config import Settings

GLOBAL = "*"
_MAX_KEYS = 10_000


class RateLimited(Exception):
    def __init__(self, retry_after: int, global_cap: bool = False):
        super().__init__("Too many requests")
        self.retry_after = retry_after
        self.global_cap = global_cap


class Limiter:
    """At most `limit` hits per `window` seconds for each key. limit <= 0 turns it off."""

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str, global_cap: bool = False) -> None:
        if self.limit <= 0:
            return
        now = self.clock()
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            raise RateLimited(max(1, math.ceil(hits[0] + self.window - now)), global_cap)
        hits.append(now)
        if len(self._hits) > _MAX_KEYS:
            self._prune(now)

    def _prune(self, now: float) -> None:
        for key in [k for k, h in self._hits.items() if not h or h[-1] <= now - self.window]:
            del self._hits[key]


class Limits:
    """The app's limits, built from settings."""

    def __init__(self, settings: Settings, clock: Callable[[], float] = time.monotonic):
        s = settings
        self.trust_proxy = s.trust_proxy
        self.search = Limiter(s.limit_search_per_minute, 60, clock)
        self.build = Limiter(s.limit_builds_per_hour, 3600, clock)
        self.ask = Limiter(s.limit_asks_per_hour, 3600, clock)
        self.builds_today = Limiter(s.limit_builds_per_day, 86400, clock)
        self.asks_today = Limiter(s.limit_asks_per_day, 86400, clock)

    def check_search(self, ip: str) -> None:
        self.search.hit(ip)

    def check_build(self, ip: str) -> None:
        """Called only when a new report build (with Claude calls) would start."""
        self.build.hit(ip)
        self.builds_today.hit(GLOBAL, global_cap=True)

    def check_ask(self, ip: str) -> None:
        self.ask.hit(ip)
        self.asks_today.hit(GLOBAL, global_cap=True)
