"""F2.1 기술지표 스키마."""
from pydantic import BaseModel


class IndicatorsRequest(BaseModel):
    ticker: str
    days: int = 60


class BollingerBands(BaseModel):
    upper: float
    middle: float
    lower: float
    bandwidth: float


class MACD(BaseModel):
    macd: float
    signal: float
    histogram: float


class IndicatorsResponse(BaseModel):
    ticker: str
    timestamp: str
    close: float
    rsi: float | None
    macd: MACD | None
    bollinger: BollingerBands | None
    ema_20: float | None
    sma_50: float | None
    atr: float | None
    vwap_20: float | None = None
    close_pct: float | None = None
    signal: str
