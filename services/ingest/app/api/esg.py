"""D-1: ESG 점수 API — GET /esg/{ticker}."""
from fastapi import APIRouter, HTTPException

from app.services.esg_store import get_esg_score

router = APIRouter(prefix="/esg", tags=["esg"])


@router.get("/{ticker}")
def esg_score(ticker: str) -> dict:
    """종목 ESG 프록시 점수 조회 (E·S·G 세부, 0~100, 6시간 캐시).

    KRX OPEN API 무료 티어 ESG 데이터 미제공 → FDR 재무 프록시 점수.
    """
    if not ticker or len(ticker) > 12:
        raise HTTPException(status_code=400, detail="ticker 형식 오류")
    return get_esg_score(ticker.upper())
