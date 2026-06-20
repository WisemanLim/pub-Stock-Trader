"""F2.1 기술지표 API."""
from fastapi import APIRouter, HTTPException

from app.schemas.indicators import IndicatorsResponse
from app.services.indicators import compute_indicators

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("/{ticker}", response_model=IndicatorsResponse)
def get_indicators(ticker: str, days: int = 60) -> IndicatorsResponse:
    """RSI·MACD·Bollinger·EMA·SMA·ATR 기술지표 + 매매 시그널."""
    try:
        data = compute_indicators(ticker.upper(), days=days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IndicatorsResponse(**data)
