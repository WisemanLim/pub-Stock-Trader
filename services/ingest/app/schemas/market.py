"""Market data Pydantic schemas (F1)."""
from pydantic import BaseModel


class PriceResponse(BaseModel):
    ticker: str
    price: float
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    timestamp: str
    source: str = "FinanceDataReader"


class OHLCVBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class OHLCVResponse(BaseModel):
    ticker: str
    bars: list[OHLCVBar]
    count: int


class TickersResponse(BaseModel):
    market: str
    count: int
    tickers: list[dict]
