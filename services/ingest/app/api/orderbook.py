"""F1.2 호가창 API."""
from fastapi import APIRouter, HTTPException

from app.schemas.orderbook import OrderBookResponse
from app.services.orderbook import get_orderbook
from app.services.redis_streams import publisher

router = APIRouter(prefix="/orderbook", tags=["orderbook"])


@router.get("/{ticker}", response_model=OrderBookResponse)
def get_order_book(ticker: str, levels: int = 10) -> OrderBookResponse:
    """호가창 조회 (기본 10레벨). levels=20 으로 20호가 요청 가능."""
    if levels not in (5, 10, 20):
        levels = 10
    try:
        data = get_orderbook(ticker.upper(), levels=levels)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    publisher.publish_tick(ticker.upper(), {"type": "orderbook", **data})
    return OrderBookResponse(**data)
