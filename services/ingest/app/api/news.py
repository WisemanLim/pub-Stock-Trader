"""F1.3 뉴스 API."""
from fastapi import APIRouter, HTTPException

from app.schemas.news import NewsItem, NewsResponse
from app.services.news_crawler import fetch_feed, list_sources
from app.services.redis_streams import publisher

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/sources")
def get_sources() -> list[str]:
    """지원하는 뉴스 소스 목록."""
    return list_sources()


@router.get("/{source}", response_model=NewsResponse)
def get_news(source: str, limit: int = 20) -> NewsResponse:
    """RSS 뉴스 조회. source: reuters-business | marketwatch | investing-kr | naver-finance."""
    try:
        items_raw = fetch_feed(source, max_items=min(limit, 50))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    for item in items_raw:
        publisher.publish_news(source, item)
    return NewsResponse(
        source=source,
        count=len(items_raw),
        items=[NewsItem(**it) for it in items_raw],
    )
