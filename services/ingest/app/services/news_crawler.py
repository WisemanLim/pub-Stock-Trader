"""F1.3 RSS 뉴스 크롤러 — feedparser 기반."""
import feedparser

RSS_FEEDS: dict[str, str] = {
    "reuters-business": "https://feeds.reuters.com/reuters/businessNews",
    "marketwatch": "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
    "investing-kr": "https://kr.investing.com/rss/news.rss",
    "naver-finance": "https://finance.naver.com/news/news_list.naver?mode=RSS",
}


def fetch_feed(source: str, max_items: int = 20) -> list[dict]:
    url = RSS_FEEDS.get(source)
    if url is None:
        raise ValueError(f"Unknown source: {source}. Available: {list(RSS_FEEDS)}")
    try:
        parsed = feedparser.parse(url)
    except Exception as exc:
        raise RuntimeError(f"RSS fetch failed: {exc}") from exc

    items = []
    for entry in parsed.entries[:max_items]:
        items.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "summary": entry.get("summary", "")[:500],
            "source": source,
        })
    return items


def list_sources() -> list[str]:
    return list(RSS_FEEDS)
