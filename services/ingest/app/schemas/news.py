"""F1.3 뉴스 스키마."""
from pydantic import BaseModel


class NewsItem(BaseModel):
    title: str
    link: str
    published: str
    summary: str = ""
    source: str


class NewsResponse(BaseModel):
    source: str
    count: int
    items: list[NewsItem]
