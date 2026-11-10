from datetime import date

import httpx
import pytest

from app.analysis import ReviewInsight, Summary, TopicMention, phrase_counts, topic_scores
from app.config import Settings
from app.db import create_tables, make_engine, make_sessionmaker
from app.connectors import GooglePlaces, Tripadvisor
from app.models import AskAnswer, HotelCandidate, Point, Review, SourceScore
from app.normalize import overall_score, to_ten
from app.service import ReportService, dedupe


# ---------- normalization ----------


@pytest.mark.parametrize(
    "rating,scale,expected",
    [(5, 5, 10), (1, 5, 0), (3, 5, 5), (4.3, 5, 8.25), (10, 10, 10), (8.2, 10, 8.0), (None, 5, None)],
)
def test_to_ten(rating, scale, expected):
    assert to_ten(rating, scale) == expected


def _score(score, count):
    return SourceScore(
        source="x", source_label="X", rating=None, scale_max=5, score_10=score, review_count=count
    )


def test_overall_weights_by_review_count():
    big, small = _score(8.0, 2000), _score(4.0, 12)
    result = overall_score([big, small])
    assert 6.5 < result < 8.0  # pulled toward the big source, not drowned by it


def test_overall_ignores_sources_without_score():
    assert overall_score([_score(None, 50), _score(7.0, 10)]) == 7.0
    assert overall_score([]) is None


# ---------- aggregation ----------


def _insight(rid, topics, pros=(), cons=()):
    return ReviewInsight(
        review_id=rid,
        topics=[TopicMention(topic=t, sentiment=s) for t, s in topics],
        pros=list(pros),
        cons=list(cons),
    )


def test_topic_scores_counts_once_per_review_and_mixed_is_negative():
    insights = [
        _insight("a", [("staff", "positive"), ("staff", "positive"), ("noise", "negative")]),
        _insight("b", [("staff", "positive"), ("staff", "negative")]),
        _insight("c", [("staff", "positive")]),
    ]
    scores = {s.topic: s for s in topic_scores(insights)}
    assert (scores["staff"].positive, scores["staff"].negative) == (2, 1)
    assert scores["staff"].score_10 == 6.7
    assert scores["noise"].score_10 == 0
    assert "wifi" not in scores


def test_phrase_counts_once_per_review():
    pros, cons = phrase_counts(
        [_insight("a", [], pros=["Friendly staff", "friendly staff "]), _insight("b", [], ["friendly staff"])]
    )
    assert pros["friendly staff"] == 2


def test_dedupe_ignores_case_and_spacing():
    r = lambda i, t: Review(id=i, source="s", text=t)  # noqa: E731
    assert [x.id for x in dedupe([r("1", "Great  view"), r("2", "great view"), r("3", "Bad")])] == ["1", "3"]


# ---------- connectors (HTTP mocked) ----------


async def test_google_details_parses_reviews():
    def handler(request: httpx.Request):
        assert request.headers["X-Goog-Api-Key"] == "k"
        return httpx.Response(
            200,
            json={
                "id": "p1",
                "displayName": {"text": "Hotel A"},
                "formattedAddress": "Antalya",
                "rating": 4.5,
                "userRatingCount": 320,
                "googleMapsUri": "https://maps.google.com/?cid=1",
                "reviews": [
                    {
                        "rating": 5,
                        "text": {"text": "Great (translated)", "languageCode": "en"},
                        "originalText": {"text": "Harika", "languageCode": "tr"},
                        "publishTime": "2026-09-01T10:00:00Z",
                        "authorAttribution": {"displayName": "Ali"},
                    },
                    {"rating": 3},  # no text: skipped
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        hotel, result = await GooglePlaces("k", http).details("p1", "en")
    assert hotel.name == "Hotel A"
    assert result.review_count == 320
    assert [(r.text, r.language, str(r.published)) for r in result.reviews] == [
        ("Harika", "tr", "2026-09-01")
    ]


async def test_tripadvisor_fetch_matches_and_parses():
    def handler(request: httpx.Request):
        path = request.url.path
        if path.endswith("/location/search"):
            return httpx.Response(200, json={"data": [{"location_id": "99", "name": "Hotel A"}]})
        if path.endswith("/details"):
            return httpx.Response(200, json={"rating": "4.0", "num_reviews": "812", "web_url": "u"})
        if path.endswith("/reviews"):
            return httpx.Response(
                200,
                json={"data": [{"id": 7, "rating": 4, "title": "Nice", "text": "Clean rooms", "lang": "en",
                                "published_date": "2026-08-01T00:00:00Z"}]},
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await Tripadvisor("k", http).fetch(HotelCandidate(id="p1", name="Hotel A"), "en")
    assert (result.rating, result.review_count, result.external_id) == (4.0, 812, "99")
    assert result.reviews[0].text == "Nice Clean rooms"


# ---------- API (demo data, fake analyzer, temporary SQLite) ----------


class FakeAnalyzer:
    def __init__(self):
        self.summaries = 0

    async def extract(self, reviews):
        return [_insight(r.id, [("location", "positive")], pros=["near the beach"]) for r in reviews]

    async def summarize(self, hotel_name, reviews, insights, lang):
        self.summaries += 1
        return Summary(
            summary=f"{hotel_name} in {lang}",
            pros=[Point(text="near the beach", mentions=len(insights), quotes=["Lage direkt am Strand"])],
            cons=[],
        )

    async def ask(self, question, reviews, lang):
        return AskAnswer(answer=f"{len(reviews)} reviews: {question}")


@pytest.fixture
async def api(tmp_path):
    from app.main import app

    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await create_tables(engine)
    analyzer = FakeAnalyzer()
    svc = ReportService(Settings(_env_file=None), analyzer, httpx.AsyncClient(), make_sessionmaker(engine))
    app.state.service = svc
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c, svc, analyzer
    del app.state.service
    await engine.dispose()


async def test_demo_search_report_history_and_ask(api):
    client, svc, analyzer = api
    assert (await client.get("/api/health")).json()["demo_mode"] is True
    hotel_id = (await client.get("/api/hotels/search", params={"q": "antalya"})).json()[0]["id"]
    url = f"/api/hotels/{hotel_id}/report"

    assert (await client.get(url, params={"lang": "tr"})).status_code == 404  # nothing built yet
    start = await client.post(url, params={"lang": "tr"})
    assert start.status_code == 202 and start.json()["status"] == "running"
    await svc.wait_for_builds()

    job = (await client.get(url, params={"lang": "tr"})).json()
    assert job["status"] == "done"
    report = job["report"]
    assert report["lang"] == "tr"
    assert [s["source"] for s in report["sources"]] == ["google", "tripadvisor"]
    assert report["analyzed_reviews"] == 13
    assert report["topics"][0] == {"topic": "location", "score_10": 10.0, "positive": 13, "negative": 0}
    assert 7 < report["overall_score_10"] < 9

    # A fresh report is served from the database without rebuilding.
    again = await client.post(url, params={"lang": "tr"})
    assert again.status_code == 200 and again.json()["status"] == "done"
    assert analyzer.summaries == 1

    history = (await client.get(f"/api/hotels/{hotel_id}/history")).json()
    assert [h["source"] for h in history] == ["google", "tripadvisor"]
    assert history[0]["score_10"] == 8.25

    answer = (await client.post(f"/api/hotels/{hotel_id}/ask", json={"question": "Is it quiet?"})).json()
    assert answer["answer"] == "13 reviews: Is it quiet?"


async def test_same_day_snapshot_is_replaced(api):
    _, svc, _ = api
    s = lambda score: SourceScore(source="google", source_label="G", rating=None, scale_max=5,  # noqa: E731
                                  score_10=score, review_count=10)
    await svc._record_scores("h1", [s(6.0)], day=date(2026, 11, 1))
    await svc._record_scores("h1", [s(7.0)], day=date(2026, 11, 1))
    await svc._record_scores("h1", [s(8.0)], day=date(2026, 11, 2))
    assert [(str(p.day), p.score_10) for p in await svc.history("h1")] == [
        ("2026-11-01", 7.0),
        ("2026-11-02", 8.0),
    ]


async def test_unknown_hotel_build_fails(api):
    client, svc, _ = api
    await client.post("/api/hotels/demo:nope/report")
    await svc.wait_for_builds()
    job = (await client.get("/api/hotels/demo:nope/report")).json()
    assert job == {"status": "failed", "report": None, "error": "Hotel not found"}
