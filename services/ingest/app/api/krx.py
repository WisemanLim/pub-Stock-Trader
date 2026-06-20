"""F1.5 KRX OPEN API 엔드포인트 + B-1 시장경보 + B-3 공매도."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from app.core.config import settings
from app.services.alert_store import get_active_alerts, upsert_alerts
from app.services.krx_openapi import KrxOpenApiService
from app.services.market_alert_service import KrxMarketAlertService
from app.services.shortsell_store import get_short_selling as db_short_selling
from app.services.shortsell_store import upsert_short_selling

router = APIRouter(prefix="/krx", tags=["krx"])

# ── 종목 목록 캐시 (FDR 기반) ──────────────────────────────────────────────
_stock_cache: list[dict] = []
_stock_cache_at: datetime | None = None
_stock_lock = threading.Lock()
_CACHE_TTL = timedelta(hours=24)
_CACHE_FAIL_TTL = timedelta(minutes=5)  # 실패 시 재시도 간격


def _get_stock_list() -> list[dict]:
    """KRX 전종목 (KOSPI+KOSDAQ) 캐시. 성공 TTL 24h, 실패 TTL 5m."""
    global _stock_cache, _stock_cache_at
    with _stock_lock:
        if _stock_cache_at and datetime.utcnow() - _stock_cache_at < _CACHE_TTL:
            return _stock_cache
        try:
            import FinanceDataReader as fdr

            def _to_rows(df, market: str) -> list[dict]:
                name_col = next((c for c in ["Name", "name"] if c in df.columns), None)
                code_col = next((c for c in ["Code", "Symbol", "symbol"] if c in df.columns), None)
                if not name_col or not code_col:
                    return []
                return [
                    {"ticker": str(r[code_col]).strip(), "name": str(r[name_col]).strip(), "market": market}
                    for _, r in df.iterrows()
                    if str(r.get(code_col, "")).strip()
                ]

            rows: list[dict] = []
            for mkt in ("KOSPI", "KOSDAQ"):
                try:
                    rows.extend(_to_rows(fdr.StockListing(mkt), mkt))
                except Exception:
                    pass
            if rows:
                _stock_cache = rows
                _stock_cache_at = datetime.utcnow()
            else:
                # FDR 실패(봇차단 등) — 5분 후 재시도되도록 타임스탬프 설정
                _stock_cache_at = datetime.utcnow() - (_CACHE_TTL - _CACHE_FAIL_TTL)
        except Exception:
            _stock_cache_at = datetime.utcnow() - (_CACHE_TTL - _CACHE_FAIL_TTL)
        return _stock_cache

_svc = KrxOpenApiService(
    api_key=settings.krx_open_api_key,
    rate_limit=settings.krx_api_rate_limit,
)


def _default_range(days: int = 30) -> tuple[str, str]:
    today = datetime.today()
    return (
        (today - timedelta(days=days)).strftime("%Y%m%d"),
        today.strftime("%Y%m%d"),
    )


@router.get("/stocks/search")
def search_stocks(
    q: str = Query(default="", description="종목코드(숫자) 또는 기업명"),
    market: str = Query(default="all", description="KOSPI | KOSDAQ | all"),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """KRX 전종목 검색 (FinanceDataReader 기반, 24h 캐시).

    숫자 입력 → ticker 전방매칭, 텍스트 → 기업명 포함 매칭.
    FDR 미사용/오류 시 빈 리스트 반환.
    """
    all_stocks = _get_stock_list()
    q = q.strip()
    if not q:
        filtered = all_stocks
    elif q.isdigit():
        filtered = [s for s in all_stocks if s["ticker"].startswith(q)]
    else:
        ql = q.lower()
        filtered = [s for s in all_stocks if ql in s["name"].lower()]

    if market.upper() != "ALL":
        filtered = [s for s in filtered if s["market"].upper() == market.upper()]

    return {
        "query": q,
        "results": filtered[:limit],
        "count": len(filtered[:limit]),
        "total_listed": len(all_stocks),
        "cached": _stock_cache_at is not None,
    }


@router.get("/stocks/{ticker}")
def get_stock_info(ticker: str) -> dict:
    """단일 종목 정보 (ticker 정확 매칭)."""
    all_stocks = _get_stock_list()
    found = next((s for s in all_stocks if s["ticker"] == ticker.upper()), None)
    if found:
        return {"found": True, **found}
    return {"found": False, "ticker": ticker.upper(), "name": None, "market": None}


@router.get("/status")
def krx_status() -> dict:
    """KRX OPEN API 키 설정 여부."""
    return {
        "configured": _svc.configured,
        "note": "KRX_OPEN_API_KEY 환경변수 설정 시 활성화됩니다." if not _svc.configured else "KRX OPEN API 활성화됨.",
    }


@router.get("/ohlcv/{ticker}")
def get_krx_ohlcv(
    ticker: str,
    from_date: str = Query(default="", description="YYYYMMDD, 미지정 시 30일 전"),
    to_date:   str = Query(default="", description="YYYYMMDD, 미지정 시 오늘"),
    market:    str = Query(default="KOSPI", description="KOSPI | KOSDAQ | KONEX"),
) -> dict:
    """KRX OPEN API — 일별 OHLCV.

    API 키 미설정 시 빈 bars 반환(configured=false).
    """
    if not _svc.configured:
        return {"ticker": ticker.upper(), "configured": False, "bars": [], "count": 0}

    fd, td = _default_range() if not from_date else (from_date, to_date or datetime.today().strftime("%Y%m%d"))
    if from_date:
        fd, td = from_date, to_date or datetime.today().strftime("%Y%m%d")

    bars = _svc.get_daily_ohlcv(ticker.upper(), fd, td, market.upper())
    return {"ticker": ticker.upper(), "configured": True, "bars": bars, "count": len(bars)}


@router.get("/investor-flow/{ticker}")
def get_investor_flow(
    ticker:    str,
    from_date: str = Query(default="", description="YYYYMMDD"),
    to_date:   str = Query(default="", description="YYYYMMDD"),
) -> dict:
    """KRX OPEN API — 투자자별 순매수 (기관/외국인/개인).

    API 키 미설정 시 빈 flows 반환(configured=false).
    미설정 환경에서도 mock 데이터로 UI 개발 가능하도록 phase='A_pending' 표시.
    """
    if not _svc.configured:
        return {
            "ticker": ticker.upper(),
            "configured": False,
            "phase": "A_pending",
            "flows": [],
            "count": 0,
        }

    fd, td = _default_range() if not from_date else (from_date, to_date or datetime.today().strftime("%Y%m%d"))

    flows = _svc.get_investor_flow(ticker.upper(), fd, td)
    if not flows:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No investor flow data for {ticker}")

    return {"ticker": ticker.upper(), "configured": True, "flows": flows, "count": len(flows)}


# ── B-1: KRX 시장경보 종목 수집기 ────────────────────────────────────────

_alert_svc = KrxMarketAlertService()


@router.get("/market-alerts")
def get_market_alerts(
    ticker: str = Query(default="", description="종목코드 필터 (미지정 시 전체)"),
    fetch: bool = Query(default=False, description="true 시 KIND 실시간 수집 후 DB 저장"),
) -> dict:
    """KRX 시장경보 종목 (투자주의/경고/위험/정리매매).

    - fetch=false (기본): DB 저장분 반환
    - fetch=true: KIND 실시간 수집 → DB 저장 → 반환
    """
    if fetch:
        raw = _alert_svc.get_alert_stocks()
        saved = upsert_alerts(raw)
        alerts = get_active_alerts(ticker.upper() if ticker else None)
        return {"fetched": len(raw), "saved": saved, "alerts": alerts, "count": len(alerts)}

    alerts = get_active_alerts(ticker.upper() if ticker else None)
    return {"fetched": 0, "saved": 0, "alerts": alerts, "count": len(alerts)}


@router.post("/market-alerts/sync")
def sync_market_alerts() -> dict:
    """KIND에서 시장경보 목록을 즉시 수집하고 DB에 저장."""
    raw = _alert_svc.get_alert_stocks()
    saved = upsert_alerts(raw)
    return {"fetched": len(raw), "saved": saved, "status": "ok"}


# ── B-3: 공매도 일별 통계 ─────────────────────────────────────────────────

@router.get("/short-selling/{ticker}")
def get_short_selling_endpoint(
    ticker: str,
    from_date: str = Query(default="", description="YYYYMMDD"),
    to_date:   str = Query(default="", description="YYYYMMDD"),
    fetch: bool = Query(default=False, description="true 시 KRX OPEN API 수집 후 DB 저장"),
) -> dict:
    """공매도 일별 통계.

    - fetch=false (기본): DB 저장분 반환
    - fetch=true + API 키 설정: KRX OPEN API 수집 → DB 저장 → 반환
    """
    t = ticker.upper()
    if fetch and _svc.configured:
        fd, td = _default_range(30) if not from_date else (from_date, to_date or datetime.today().strftime("%Y%m%d"))
        rows = _svc.get_short_selling(t, fd, td)
        saved = upsert_short_selling(t, rows)
        data = db_short_selling(t)
        return {"ticker": t, "configured": True, "fetched": len(rows), "saved": saved, "data": data, "count": len(data)}

    data = db_short_selling(t)
    return {"ticker": t, "configured": _svc.configured, "fetched": 0, "saved": 0, "data": data, "count": len(data)}
