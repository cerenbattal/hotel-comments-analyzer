import pytest

from app.config import Settings
from app.main import app
from app.ratelimit import Limiter, Limits, RateLimited
from test_core import api  # noqa: F401  (shared fixture)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_sliding_window_and_retry_after():
    clock = Clock()
    lim = Limiter(2, 60, clock)
    lim.hit("a")
    clock.now += 10
    lim.hit("a")
    lim.hit("b")  # other keys have their own window
    with pytest.raises(RateLimited) as e:
        lim.hit("a")
    assert e.value.retry_after == 50  # until the first hit leaves the window
    clock.now += 50
    lim.hit("a")


def test_zero_turns_a_limit_off():
    lim = Limiter(0, 60)
    for _ in range(100):
        lim.hit("a")


def _limits(**overrides):
    return Limits(Settings(_env_file=None, **overrides))


async def test_only_new_builds_count(api):
    client, svc, _ = api
    app.state.limits = _limits(limit_builds_per_hour=1)
    assert (await client.post("/api/hotels/demo:seaside/report")).status_code == 202
    await svc.wait_for_builds()
    # The finished report is served from the database and costs nothing.
    assert (await client.post("/api/hotels/demo:seaside/report")).status_code == 200
    refused = await client.post("/api/hotels/demo:harbor/report")
    assert refused.status_code == 429
    assert int(refused.headers["retry-after"]) > 3500
    # No build row was left behind for the refused request.
    assert (await client.get("/api/hotels/demo:harbor/report")).status_code == 404


async def test_daily_cap_is_shared_by_everyone(api):
    client, _, _ = api
    app.state.limits = _limits(limit_asks_per_day=1)
    body = {"question": "Is it quiet?"}
    assert (await client.post("/api/hotels/demo:seaside/ask", json=body)).status_code == 200
    other = {"x-forwarded-for": "203.0.113.9"}  # ignored: proxy headers are not trusted by default
    refused = await client.post("/api/hotels/demo:seaside/ask", json=body, headers=other)
    assert refused.status_code == 503


async def test_search_limit_per_ip_behind_a_trusted_proxy(api):
    client, _, _ = api
    app.state.limits = _limits(limit_search_per_minute=1, trust_proxy=True)
    url, q = "/api/hotels/search", {"q": "antalya"}
    assert (await client.get(url, params=q, headers={"x-forwarded-for": "198.51.100.1"})).status_code == 200
    assert (await client.get(url, params=q, headers={"x-forwarded-for": "198.51.100.1"})).status_code == 429
    assert (await client.get(url, params=q, headers={"x-forwarded-for": "198.51.100.2"})).status_code == 200
