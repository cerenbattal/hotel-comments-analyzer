from datetime import date

from app.analysis import ReviewInsight, TopicMention
from app.connectors.demo import demo_data
from app.models import Review, SourceScore
from app.normalize import source_score
from app.trust import (
    assess,
    duplicate_text,
    five_star_burst,
    rating_text_mismatch,
    short_five_star,
    source_gap,
)


def _review(i, text="A pleasant stay with a nice view of the old harbor", rating=5, day=None, source="google"):
    return Review(id=f"{source}:{i}", source=source, rating=rating, scale_max=5, text=text,
                  published=date(2026, 9, day) if day else None)


def _score(label, score, count=100):
    return SourceScore(source=label.lower(), source_label=label, rating=None, scale_max=5,
                       score_10=score, review_count=count)


def test_source_gap_flags_only_the_outlier():
    flags = source_gap([_score("Google", 9.5), _score("Tripadvisor", 7.0), _score("Booking", 7.4)])
    assert [(f.source, f.gap) for f in flags] == [("Google", 2.3)]
    assert source_gap([_score("Google", 8.0), _score("Tripadvisor", 7.0)]) == []
    assert source_gap([_score("Google", 9.5)]) == []  # nothing to compare with


def test_five_star_burst():
    burst = [_review(i, rating=5, day=d) for i, d in enumerate([1, 2, 3, 3])] + [
        _review(9, rating=3, day=20), _review(10, rating=4, day=28)]
    flags = five_star_burst(burst, {"google": "Google Maps"})
    assert [(f.source, f.count, f.total) for f in flags] == [("Google Maps", 4, 6)]
    spread = [_review(i, rating=5, day=d) for i, d in enumerate([1, 8, 15, 22, 29])]
    assert five_star_burst(spread) == []
    assert five_star_burst(burst[:4]) == []  # too few reviews to judge


def test_duplicate_text_ignores_different_and_short_texts():
    text = "Great hotel, friendly staff and the breakfast was really amazing every single day"
    flags = duplicate_text([_review(1, text), _review(2, text + "!"), _review(3, "Room was small but clean and quiet at night")])
    assert [(f.count, f.total) for f in flags] == [(2, 3)]
    assert duplicate_text([_review(1, "Great!"), _review(2, "Great!")]) == []


def _insight(rid, pos, neg):
    return ReviewInsight(
        review_id=rid,
        topics=[TopicMention(topic=t, sentiment="positive") for t in pos]
        + [TopicMention(topic=t, sentiment="negative") for t in neg],
        pros=[], cons=[],
    )


def test_rating_text_mismatch():
    reviews = [_review(1, rating=5), _review(2, rating=1), _review(3, rating=5), _review(4, rating=4)]
    insights = [
        _insight("google:1", [], ["noise", "wifi"]),  # 5 stars, only complaints
        _insight("google:2", ["staff", "location"], []),  # 1 star, only praise
        _insight("google:3", ["staff"], ["noise"]),  # mixed: fine
        _insight("google:4", [], ["noise", "room"]),  # 4 stars is not top rating
    ]
    assert [(f.count, f.total) for f in rating_text_mismatch(reviews, insights)] == [(2, 4)]


def test_short_five_star():
    reviews = [_review(i, "Super!", 5) for i in range(3)] + [_review(i + 10) for i in range(3)]
    assert [(f.count, f.total) for f in short_five_star(reviews)] == [(3, 6)]
    assert short_five_star(reviews[:3] + [_review(i + 10) for i in range(7)]) == []  # 3 of 10


def _demo_trust(hotel_id):
    _, sources = demo_data(hotel_id)
    reviews = [r for s in sources for r in s.reviews]
    return assess([source_score(s) for s in sources], reviews, [])


def test_honest_demo_hotels_raise_no_flags():
    for hotel_id in ("demo:seaside", "demo:harbor"):
        trust = _demo_trust(hotel_id)
        assert trust.level == "ok", (hotel_id, trust.flags)


def test_suspicious_demo_hotel_is_flagged():
    trust = _demo_trust("demo:sunrise")
    assert trust.level == "caution"
    assert {f.code for f in trust.flags} == {
        "source_gap", "five_star_burst", "duplicate_text", "short_five_star"
    }
