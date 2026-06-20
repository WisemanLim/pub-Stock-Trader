"""F5 백테스팅 엔진 — 다전략 + 수수료·슬리피지 반영 성과 측정.

전략(strategy)은 종가 시퀀스 → 목표 포지션 배열(1=롱, 0=현금) 생성.
실행 루프는 전략 무관(롱온리). 성과지표: 총수익률·MDD·Sharpe·Sortino·승률·손익비.
"""
from datetime import datetime, timedelta, timezone

import FinanceDataReader as fdr
import numpy as np

TRADING_DAYS = 252
STRATEGIES = ("sma_cross", "rsi_threshold", "macd_cross")


def _sma(arr: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return arr.copy()
    out = np.full_like(arr, np.nan, dtype=float)
    cs = np.cumsum(np.insert(arr, 0, 0.0))
    out[window - 1 :] = (cs[window:] - cs[:-window]) / window
    return out


def _ema(arr: np.ndarray, window: int) -> np.ndarray:
    alpha = 2.0 / (window + 1)
    out = np.empty_like(arr, dtype=float)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def _rsi(arr: np.ndarray, period: int = 14) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=float)
    if len(arr) <= period:
        return out
    delta = np.diff(arr)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    for i in range(period, len(arr)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gain[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + loss[i - 1]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 0.0
        out[i] = 100.0 - 100.0 / (1.0 + rs) if avg_loss > 0 else 100.0
    return out


# ── 전략: 종가 → 목표 포지션 배열 (1=롱, 0=현금) ──

def _strat_sma_cross(px: np.ndarray, p: dict) -> np.ndarray:
    short = _sma(px, p.get("short_window", 5))
    long = _sma(px, p.get("long_window", 20))
    pos = np.zeros(len(px))
    for i in range(len(px)):
        if not np.isnan(short[i]) and not np.isnan(long[i]):
            pos[i] = 1.0 if short[i] > long[i] else 0.0
    return pos


def _strat_rsi_threshold(px: np.ndarray, p: dict) -> np.ndarray:
    period = p.get("rsi_period", 14)
    buy_below = p.get("rsi_buy_below", 30.0)
    sell_above = p.get("rsi_sell_above", 70.0)
    rsi = _rsi(px, period)
    pos = np.zeros(len(px))
    holding = 0.0
    for i in range(len(px)):
        if np.isnan(rsi[i]):
            pos[i] = holding
            continue
        if rsi[i] < buy_below:
            holding = 1.0
        elif rsi[i] > sell_above:
            holding = 0.0
        pos[i] = holding
    return pos


def _strat_macd_cross(px: np.ndarray, p: dict) -> np.ndarray:
    fast = _ema(px, p.get("macd_fast", 12))
    slow = _ema(px, p.get("macd_slow", 26))
    macd = fast - slow
    signal = _ema(macd, p.get("macd_signal", 9))
    pos = np.zeros(len(px))
    for i in range(len(px)):
        pos[i] = 1.0 if macd[i] > signal[i] else 0.0
    return pos


_STRATEGY_FN = {
    "sma_cross": _strat_sma_cross,
    "rsi_threshold": _strat_rsi_threshold,
    "macd_cross": _strat_macd_cross,
}


def run_backtest(
    closes: list[float],
    strategy: str = "sma_cross",
    params: dict | None = None,
    fee_bps: float = 5.0,
    slippage_bps: float = 5.0,
    initial_capital: float = 10_000_000.0,
    warmup: int = 26,
) -> dict:
    """전략 기반 롱온리 백테스트. closes: 종가 시퀀스(시간순)."""
    if strategy not in _STRATEGY_FN:
        raise ValueError(f"Unknown strategy: {strategy}. Valid: {list(_STRATEGY_FN)}")
    if len(closes) < warmup + 2:
        raise ValueError(f"Insufficient data: {len(closes)} < {warmup + 2}")

    px = np.asarray(closes, dtype=float)
    target = _STRATEGY_FN[strategy](px, params or {})

    cost_rate = (fee_bps + slippage_bps) / 10_000.0
    cash = initial_capital
    shares = 0.0
    in_pos = False
    entry_value = 0.0
    equity_curve = []
    trade_returns = []

    for i in range(len(px)):
        if i >= warmup:
            want_long = target[i] >= 0.5
            if want_long and not in_pos:
                fill = px[i] * (1 + cost_rate)
                shares = cash / fill
                entry_value = cash
                cash = 0.0
                in_pos = True
            elif not want_long and in_pos:
                fill = px[i] * (1 - cost_rate)
                cash = shares * fill
                trade_returns.append(cash / entry_value - 1.0)
                shares = 0.0
                in_pos = False
        equity_curve.append(cash + shares * px[i])

    final_equity = equity_curve[-1]
    eq = np.asarray(equity_curve)
    daily_ret = np.diff(eq) / eq[:-1]
    daily_ret = daily_ret[np.isfinite(daily_ret)]

    total_return = final_equity / initial_capital - 1.0
    running_max = np.maximum.accumulate(eq)
    drawdown = (eq - running_max) / running_max
    mdd = float(drawdown.min()) if len(drawdown) else 0.0

    if len(daily_ret) > 1 and daily_ret.std() > 0:
        sharpe = float(daily_ret.mean() / daily_ret.std() * np.sqrt(TRADING_DAYS))
    else:
        sharpe = 0.0
    downside = daily_ret[daily_ret < 0]
    if len(downside) > 1 and downside.std() > 0:
        sortino = float(daily_ret.mean() / downside.std() * np.sqrt(TRADING_DAYS))
    else:
        sortino = 0.0

    wins = [r for r in trade_returns if r > 0]
    losses = [r for r in trade_returns if r <= 0]
    win_rate = len(wins) / len(trade_returns) if trade_returns else 0.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

    return {
        "strategy": strategy,
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return * 100, 4),
        "max_drawdown_pct": round(mdd * 100, 4),
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "num_trades": len(trade_returns),
    }


def backtest_ticker(
    ticker: str,
    days: int = 365,
    strategy: str = "sma_cross",
    params: dict | None = None,
    fee_bps: float = 5.0,
    slippage_bps: float = 5.0,
    initial_capital: float = 10_000_000.0,
) -> dict:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"))
    if df.empty:
        raise ValueError(f"No data for ticker: {ticker}")
    closes = df["Close"].astype(float).tolist()
    result = run_backtest(
        closes, strategy, params, fee_bps, slippage_bps, initial_capital
    )
    result["ticker"] = ticker
    result["bars"] = len(closes)
    return result
