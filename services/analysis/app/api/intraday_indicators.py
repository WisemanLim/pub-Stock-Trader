"""D-4: 분봉 기반 기술지표 API — GET /indicators/intraday/{ticker}."""
from fastapi import APIRouter, Query

from app.services.intraday_indicators import calc_intraday_indicators

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("/intraday/{ticker}")
def intraday_indicators(
    ticker: str,
    interval: str = Query(default="5m", description="1m | 5m"),
) -> dict:
    """분봉(1m/5m) 기반 RSI·MACD·VWAP 지표.

    ingest 서비스의 /market/intraday/{ticker} 에서 분봉 데이터를 받아 계산.
    ingest 미기동 시 available=false 반환.
    """
    return calc_intraday_indicators(ticker.upper(), interval)
