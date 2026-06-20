"""F5 강화학습 백테스팅 — 테이블 Q-learning 에이전트.

상태: (RSI 버킷 0..4, 보유여부 0/1). 행동: 0=보유, 1=매수, 2=매도.
보상: 스텝별 자산 변화. 시드 고정 → 결정적(감사 가능).
tensortrade 대비 경량 — 의존성 없이 순수 numpy. 강화학습 전략 평가용.
"""
from datetime import datetime, timedelta, timezone

import FinanceDataReader as fdr
import numpy as np

from app.services.backtest import _rsi

TRADING_DAYS = 252
N_RSI_BUCKETS = 5
ACTIONS = 3  # hold, buy, sell


def _rsi_bucket(rsi: float) -> int:
    if np.isnan(rsi):
        return 2
    return min(N_RSI_BUCKETS - 1, max(0, int(rsi // 20)))


def _state(rsi: float, holding: int) -> int:
    return _rsi_bucket(rsi) * 2 + holding


def rl_backtest(
    closes: list[float],
    episodes: int = 50,
    alpha: float = 0.1,
    gamma: float = 0.95,
    epsilon: float = 0.1,
    fee_bps: float = 5.0,
    slippage_bps: float = 5.0,
    initial_capital: float = 10_000_000.0,
    seed: int = 42,
    warmup: int = 15,
) -> dict:
    """Q-learning 학습 후 그리디 정책 백테스트."""
    if len(closes) < warmup + 5:
        raise ValueError(f"Insufficient data: {len(closes)} < {warmup + 5}")

    px = np.asarray(closes, dtype=float)
    rsi = _rsi(px, 14)
    rng = np.random.default_rng(seed)
    cost = (fee_bps + slippage_bps) / 10_000.0

    n_states = N_RSI_BUCKETS * 2
    Q = np.zeros((n_states, ACTIONS))

    def step_reward(action: int, i: int, holding: int, entry: float) -> tuple[int, float, float]:
        """행동 적용 → (새 holding, 보상, 새 entry)."""
        reward = 0.0
        if action == 1 and holding == 0:  # buy
            holding = 1
            entry = px[i] * (1 + cost)
        elif action == 2 and holding == 1:  # sell
            reward = (px[i] * (1 - cost) - entry) / entry
            holding = 0
            entry = 0.0
        elif holding == 1:  # hold position → 평가 보상
            reward = (px[i] - px[i - 1]) / px[i - 1]
        return holding, reward, entry

    # ── 학습 ──
    for _ in range(episodes):
        holding, entry = 0, 0.0
        for i in range(warmup, len(px) - 1):
            s = _state(rsi[i], holding)
            if rng.random() < epsilon:
                a = int(rng.integers(ACTIONS))
            else:
                a = int(np.argmax(Q[s]))
            holding, r, entry = step_reward(a, i, holding, entry)
            s2 = _state(rsi[i + 1], holding)
            Q[s, a] += alpha * (r + gamma * np.max(Q[s2]) - Q[s, a])

    # ── 그리디 평가 ──
    cash, shares, holding, entry_val = initial_capital, 0.0, 0, 0.0
    equity_curve, trade_returns = [], []
    for i in range(len(px)):
        if warmup <= i < len(px):
            s = _state(rsi[i], holding)
            a = int(np.argmax(Q[s]))
            if a == 1 and holding == 0:
                fill = px[i] * (1 + cost)
                shares = cash / fill
                entry_val = cash
                cash = 0.0
                holding = 1
            elif a == 2 and holding == 1:
                fill = px[i] * (1 - cost)
                cash = shares * fill
                trade_returns.append(cash / entry_val - 1.0)
                shares = 0.0
                holding = 0
        equity_curve.append(cash + shares * px[i])

    eq = np.asarray(equity_curve)
    final_equity = float(eq[-1])
    daily_ret = np.diff(eq) / eq[:-1]
    daily_ret = daily_ret[np.isfinite(daily_ret)]
    total_return = final_equity / initial_capital - 1.0
    running_max = np.maximum.accumulate(eq)
    mdd = float(((eq - running_max) / running_max).min()) if len(eq) else 0.0
    sharpe = (
        float(daily_ret.mean() / daily_ret.std() * np.sqrt(TRADING_DAYS))
        if len(daily_ret) > 1 and daily_ret.std() > 0 else 0.0
    )
    wins = [r for r in trade_returns if r > 0]
    win_rate = len(wins) / len(trade_returns) if trade_returns else 0.0

    return {
        "strategy": "qlearn",
        "episodes": episodes,
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return * 100, 4),
        "max_drawdown_pct": round(mdd * 100, 4),
        "sharpe": round(sharpe, 4),
        "win_rate": round(win_rate, 4),
        "num_trades": len(trade_returns),
    }


def rl_backtest_ticker(
    ticker: str,
    days: int = 365,
    episodes: int = 50,
    epsilon: float = 0.1,
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
    result = rl_backtest(
        closes, episodes=episodes, epsilon=epsilon,
        fee_bps=fee_bps, slippage_bps=slippage_bps, initial_capital=initial_capital,
    )
    result["ticker"] = ticker
    result["bars"] = len(closes)
    return result
