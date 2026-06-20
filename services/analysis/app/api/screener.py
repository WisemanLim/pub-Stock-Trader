"""F2.3 종목 스크리너 API."""
from fastapi import APIRouter, HTTPException

from app.schemas.screener import ScreenerFilter, ScreenerResponse
from app.services.screener import screen

router = APIRouter(prefix="/screener", tags=["screener"])


@router.post("/", response_model=ScreenerResponse)
def run_screener(filters: ScreenerFilter) -> ScreenerResponse:
    """RSI·거래량·공매도 필터 기반 종목 스크리닝 (C-5: 80종, C-6: short_ratio)."""
    try:
        data = screen(
            market=filters.market.upper(),
            rsi_min=filters.rsi_min,
            rsi_max=filters.rsi_max,
            min_volume=filters.min_volume,
            limit=min(filters.limit, 80),
            signal_filter=filters.signal,
            min_close=filters.min_close,
            max_close=filters.max_close,
            max_short_ratio=filters.max_short_ratio,
            min_esg_score=filters.min_esg_score,  # D-6
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScreenerResponse(**data)
