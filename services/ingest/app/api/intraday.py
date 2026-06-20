"""D-3: 분봉 데이터 API — GET /market/intraday/{ticker}."""
from fastapi import APIRouter, HTTPException, Query

from app.services.intraday import fetch_intraday

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/intraday/{ticker}")
def intraday(
    ticker: str,
    interval: str = Query(default="5m", description="1m | 5m"),
) -> dict:
    """분봉(1분/5분) 데이터 조회. 실제 분봉 API 미지원 시 일봉 다운샘플링 폴백.

    D-3: 브로커 REST 직접 연동은 KIS/eBEST API 키 필요.
    현재: FDR 시도 → 실패 시 일봉→분봉 근사 반환.
    """
    if interval not in ("1m", "5m"):
        raise HTTPException(status_code=400, detail="interval 은 1m 또는 5m")
    if not ticker or len(ticker) > 12:
        raise HTTPException(status_code=400, detail="ticker 형식 오류")
    return fetch_intraday(ticker.upper(), interval)
