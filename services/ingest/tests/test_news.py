"""F1.3 뉴스 RSS API 시험 — feedparser mock."""
from unittest.mock import patch


MOCK_FEED_ENTRIES = [
    type("E", (), {
        "title": "Fed Holds Rates Steady",
        "link": "https://example.com/1",
        "published": "Mon, 08 Jan 2024 10:00:00 +0000",
        "summary": "Federal Reserve holds interest rates.",
        "get": lambda self, k, d="": getattr(self, k, d),
    })(),
    type("E", (), {
        "title": "KOSPI Rally",
        "link": "https://example.com/2",
        "published": "Mon, 08 Jan 2024 11:00:00 +0000",
        "summary": "KOSPI surges 2% on tech gains.",
        "get": lambda self, k, d="": getattr(self, k, d),
    })(),
]


class MockParsed:
    entries = MOCK_FEED_ENTRIES


def test_list_sources(client):
    r = client.get("/news/sources")
    assert r.status_code == 200
    sources = r.json()
    assert isinstance(sources, list)
    assert "reuters-business" in sources


def test_get_news_ok(client):
    with patch("app.services.news_crawler.feedparser.parse", return_value=MockParsed()):
        r = client.get("/news/reuters-business")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "reuters-business"
    assert data["count"] == 2
    assert data["items"][0]["title"] == "Fed Holds Rates Steady"


def test_get_news_unknown_source(client):
    r = client.get("/news/nonexistent-source")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_get_news_limit(client):
    many_entries = MOCK_FEED_ENTRIES * 30

    class BigFeed:
        entries = many_entries

    with patch("app.services.news_crawler.feedparser.parse", return_value=BigFeed()):
        r = client.get("/news/reuters-business?limit=5")
    assert r.status_code == 200
    assert r.json()["count"] <= 5
