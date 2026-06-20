"""F5 백테스팅 스키마."""
from pydantic import BaseModel


class BacktestRequest(BaseModel):
    ticker: str
    days: int = 365
    strategy: str = "sma_cross"   # sma_cross | rsi_threshold | macd_cross
    params: dict = {}             # 전략별 파라미터(short_window, rsi_buy_below 등)
    fee_bps: float = 5.0
    slippage_bps: float = 5.0
    initial_capital: float = 10_000_000.0


class BacktestResponse(BaseModel):
    ticker: str
    strategy: str
    bars: int
    initial_capital: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    win_rate: float
    profit_factor: float
    num_trades: int


class RLBacktestRequest(BaseModel):
    ticker: str
    days: int = 365
    episodes: int = 50
    epsilon: float = 0.1
    fee_bps: float = 5.0
    slippage_bps: float = 5.0
    initial_capital: float = 10_000_000.0


class RLBacktestResponse(BaseModel):
    ticker: str
    strategy: str
    bars: int
    episodes: int
    initial_capital: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe: float
    win_rate: float
    num_trades: int
