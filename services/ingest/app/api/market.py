"""Market data API — F1.1 시세·OHLCV·종목목록 REST + WebSocket 스트리밍."""
import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.schemas.market import OHLCVBar, OHLCVResponse, PriceResponse, TickersResponse
from app.services.finance_reader import FinanceReaderService
from app.services.redis_streams import publisher

router = APIRouter(prefix="/market", tags=["market"])
_svc = FinanceReaderService()


@router.get("/price/{ticker}", response_model=PriceResponse)
def get_price(ticker: str) -> PriceResponse:
    """최신 종가 조회. ticker: KRX 6자리(005930) 또는 US(AAPL)."""
    try:
        data = _svc.get_price(ticker.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    publisher.publish_tick(ticker.upper(), data)
    return PriceResponse(**data)


@router.get("/ohlcv/{ticker}", response_model=OHLCVResponse)
def get_ohlcv(ticker: str, days: int = 30) -> OHLCVResponse:
    """OHLCV 봉 데이터 (기본 30일). ticker: KRX/US 공통."""
    bars_data = _svc.get_ohlcv(ticker.upper(), days=days)
    return OHLCVResponse(
        ticker=ticker.upper(),
        bars=[OHLCVBar(**b) for b in bars_data],
        count=len(bars_data),
    )


@router.get("/tickers/{market}", response_model=TickersResponse)
def get_tickers(market: str) -> TickersResponse:
    """종목 목록 (상위 100개). market: KRX | NASDAQ | NYSE | KOSPI | KOSDAQ."""
    try:
        tickers = _svc.get_stock_list(market.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TickersResponse(market=market.upper(), count=len(tickers), tickers=tickers)


@router.websocket("/stream/{ticker}")
async def stream_price(websocket: WebSocket, ticker: str) -> None:
    """WebSocket 가격 스트림 (5초 폴링). 단순 최신 종가 반복."""
    await websocket.accept()
    t = ticker.upper()
    try:
        while True:
            try:
                data = _svc.get_price(t)
                publisher.publish_tick(t, data)
                await websocket.send_json(data)
            except ValueError as exc:
                await websocket.send_json({"error": str(exc), "ticker": t})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass


@router.websocket("/feed/{ticker}")
async def stream_feed(websocket: WebSocket, ticker: str) -> None:
    """F1.2 브로커 실시간 틱 피드. BROKER_WS_URL 있으면 실연동, 없으면 시뮬레이션."""
    from app.services.broker_feed import feed

    await websocket.accept()
    t = ticker.upper()
    try:
        async for tick in feed(t, interval=1.0):
            publisher.publish_tick(t, tick)
            await websocket.send_json(tick)
    except WebSocketDisconnect:
        pass


@router.websocket("/feed_multi/{tickers}")
async def stream_feed_multi(websocket: WebSocket, tickers: str) -> None:
    """F1.2 다종목 멀티플렉싱 피드. tickers=콤마구분(예: 005930,000660)."""
    from app.services.broker_feed import feed_multi

    await websocket.accept()
    syms = [s.strip().upper() for s in tickers.split(",") if s.strip()]
    try:
        async for tick in feed_multi(syms, interval=1.0):
            publisher.publish_tick(tick["ticker"], tick)
            await websocket.send_json(tick)
    except WebSocketDisconnect:
        pass
