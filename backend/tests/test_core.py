import httpx
import pytest
from fastapi.testclient import TestClient

from app.analysis import ReviewInsight, Summary, TopicMention, phrase_counts, topic_scores
from app.config import Settings
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


# ---------- API (demo data, fake analyzer) ----------


class FakeAnalyzer:
    async def extract(self, reviews):
        return [_insight(r.id, [("location", "positive")], pros=["near the beach"]) for r in reviews]

    async def summarize(self, hotel_name, reviews, insights, lang):
        return Summary(
            summary=f"{hotel_name} in {lang}",
            pros=[Point(text="near the beach", mentions=len(insights), quotes=["Lage direkt am Strand"])],
            cons=[],
        )

    async def ask(self, question, reviews, lang):
        return AskAnswer(answer=f"{len(reviews)} reviews: {question}")


@pytest.fixture
def client():
    from app.main import app

    app.state.service = ReportService(Settings(_env_file=None), FakeAnalyzer(), httpx.AsyncClient())
    with TestClient(app) as c:
        yield c
    del app.state.service


def test_demo_search_report_and_ask(client):
    assert client.get("/api/health").json()["demo_mode"] is True
    hotels = client.get("/api/hotels/search", params={"q": "antalya"}).json()
    hotel_id = hotels[0]["id"]

    report = client.get(f"/api/hotels/{hotel_id}/report", params={"lang": "tr"}).json()
    assert report["lang"] == "tr"
    assert [s["source"] for s in report["sources"]] == ["google", "tripadvisor"]
    assert report["analyzed_reviews"] == 13
    assert report["topics"][0] == {"topic": "location", "score_10": 10.0, "positive": 13, "negative": 0}
    assert 7 < report["overall_score_10"] < 9

    answer = client.post(f"/api/hotels/{hotel_id}/ask", json={"question": "Is it quiet?"}).json()
    assert answer["answer"] == "13 reviews: Is it quiet?"


def test_unknown_hotel_is_404(client):
    assert client.get("/api/hotels/demo:nope/report").status_code == 404
