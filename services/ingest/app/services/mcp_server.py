"""FastMCP 서버 — F1.4 Claude/Gemini 연동 주식 데이터 제공.

실행: uv run mcp run app/services/mcp_server.py  (ingest 서비스 디렉터리에서)
"""
from mcp.server.fastmcp import FastMCP

from app.services.finance_reader import FinanceReaderService

mcp = FastMCP("stock-trader-ingest")
_svc = FinanceReaderService()


@mcp.tool()
def get_stock_price(ticker: str) -> dict:
    """최신 종가를 가져옵니다. ticker 예시: 005930 (삼성전자), AAPL, KS11 (KOSPI지수)."""
    try:
        return _svc.get_price(ticker.upper())
    except ValueError as exc:
        return {"error": str(exc), "ticker": ticker}


@mcp.tool()
def get_ohlcv(ticker: str, days: int = 30) -> dict:
    """OHLCV 봉 데이터를 가져옵니다. days: 조회 기간(일), 기본 30일."""
    bars = _svc.get_ohlcv(ticker.upper(), days=days)
    return {"ticker": ticker.upper(), "count": len(bars), "bars": bars}


@mcp.tool()
def list_stocks(market: str = "KRX") -> dict:
    """종목 목록(상위 100개)을 가져옵니다. market: KRX | NASDAQ | NYSE."""
    try:
        tickers = _svc.get_stock_list(market.upper())
        return {"market": market.upper(), "count": len(tickers), "tickers": tickers}
    except ValueError as exc:
        return {"error": str(exc), "market": market}
