"""Runs the daily score refresh inside the API process."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)


def seconds_until(hour_utc: int, now: datetime) -> float:
    """Seconds from `now` until the next time the clock reads `hour_utc`:00 UTC."""
    target = now.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def run_daily(job, hour_utc: int) -> None:
    """Call `job()` every day at `hour_utc`:00 UTC until cancelled."""
    while True:
        await asyncio.sleep(seconds_until(hour_utc, datetime.now(timezone.utc)))
        try:
            await job()
        except Exception:
            log.exception("Daily job failed")
