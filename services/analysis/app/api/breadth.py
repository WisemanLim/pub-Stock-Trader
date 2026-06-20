"""C-2: 시장 폭(Market Breadth) API — GET /breadth."""
from fastapi import APIRouter, Query

from app.services.breadth import get_breadth

router = APIRouter(prefix="/breadth", tags=["breadth"])


@router.get("/")
def market_breadth(market: str = Query(default="KOSPI", description="KOSPI | KOSDAQ | KRX")) -> dict:
    """시장 폭 지표: 상승/하락 종목수, TRIN(Arms Index), AD Line.

    30분 캐시. 최초 호출 시 수초 소요 (FDR 다종목 조회).
    """
    return get_breadth(market)
