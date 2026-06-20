"""F5 Distributional DQN (C51) 백테스팅 — 가치 분포 학습.

C51: Q값 대신 [V_min, V_max] 를 N_ATOMS 로 이산화한 분포를 예측.
projected Bellman update 로 분포 학습. 행동 = argmax E[Z]. 시드 결정적.
torch — 메인 스레드 직접 호출(테스트), HTTP 는 async 엔드포인트.
"""
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from datetime import datetime, timedelta, timezone

import FinanceDataReader as fdr
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from app.services.backtest import _rsi
from app.services.dqn_backtest import _state_vec

torch.set_num_threads(1)

TRADING_DAYS = 252
ACTIONS = 3
STATE_DIM = 3
N_ATOMS = 21


class _C51Net(nn.Module):
    """상태 → (ACTIONS, N_ATOMS) 분포 로짓."""

    def __init__(self, hidden: int = 24) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Linear(STATE_DIM, hidden), nn.ReLU())
        self.head = nn.Linear(hidden, ACTIONS * N_ATOMS)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.net(x)
        logits = self.head(h).view(-1, ACTIONS, N_ATOMS)
        return F.softmax(logits, dim=-1)  # 행동별 확률분포


def c51_backtest(
    closes: list[float],
    episodes: int = 20,
    gamma: float = 0.95,
    lr: float = 0.01,
    v_min: float = -0.1,
    v_max: float = 0.1,
    fee_bps: float = 5.0,
    slippage_bps: float = 5.0,
    initial_capital: float = 10_000_000.0,
    seed: int = 42,
    warmup: int = 15,
    batch_size: int = 32,
    target_sync: int = 50,
) -> dict:
    if len(closes) < warmup + 5:
        raise ValueError(f"Insufficient data: {len(closes)} < {warmup + 5}")

    torch.manual_seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)

    px = np.asarray(closes, dtype=float)
    rsi = _rsi(px, 14)
    cost = (fee_bps + slippage_bps) / 10_000.0

    support = torch.linspace(v_min, v_max, N_ATOMS)  # 가치 지지점
    dz = (v_max - v_min) / (N_ATOMS - 1)

    net = _C51Net()
    target = _C51Net()
    target.load_state_dict(net.state_dict())
    target.eval()
    opt = torch.optim.Adam(net.parameters(), lr=lr)

    replay: list = []

    def ret_at(i):
        return (px[i] - px[i - 1]) / px[i - 1] if i > 0 else 0.0

    def q_values(dist):  # E[Z] = Σ p·z
        return (dist * support).sum(dim=-1)

    def project(next_dist, rewards):
        """projected Bellman — Tz=r+γz 를 support 로 사영."""
        bsz = rewards.shape[0]
        proj = torch.zeros(bsz, N_ATOMS)
        for j in range(N_ATOMS):
            tz = (rewards + gamma * support[j]).clamp(v_min, v_max)
            bj = (tz - v_min) / dz
            lo = bj.floor().long()
            up = bj.ceil().long()
            for b in range(bsz):
                proj[b, lo[b]] += next_dist[b, j] * (up[b].float() - bj[b])
                proj[b, up[b]] += next_dist[b, j] * (bj[b] - lo[b].float())
        return proj

    step = 0
    for _ in range(episodes):
        holding, entry = 0, 0.0
        for i in range(warmup, len(px) - 1):
            s_vec = _state_vec(rsi[i], ret_at(i), holding)
            with torch.no_grad():
                dist = net(torch.tensor(s_vec, dtype=torch.float32).unsqueeze(0))
                a = int(q_values(dist).argmax().item())

            reward = 0.0
            if a == 1 and holding == 0:
                holding, entry = 1, px[i] * (1 + cost)
            elif a == 2 and holding == 1:
                reward = (px[i] * (1 - cost) - entry) / entry
                holding, entry = 0, 0.0
            elif holding == 1:
                reward = ret_at(i + 1)

            s2_vec = _state_vec(rsi[i + 1], ret_at(i + 1), holding)
            replay.append((s_vec, a, reward, s2_vec))
            if len(replay) > 2000:
                replay.pop(0)

            if len(replay) >= batch_size:
                idx = rng.choice(len(replay), size=batch_size, replace=False)
                batch = [replay[int(j)] for j in idx]
                ss = torch.tensor([b[0] for b in batch], dtype=torch.float32)
                aa = torch.tensor([b[1] for b in batch], dtype=torch.int64)
                rr = torch.tensor([b[2] for b in batch], dtype=torch.float32)
                ss2 = torch.tensor([b[3] for b in batch], dtype=torch.float32)

                with torch.no_grad():
                    next_dist_all = target(ss2)
                    next_a = q_values(next_dist_all).argmax(dim=1)
                    next_dist = next_dist_all[torch.arange(batch_size), next_a]
                    target_dist = project(next_dist, rr)

                dist_pred = net(ss)[torch.arange(batch_size), aa]
                loss = -(target_dist * torch.log(dist_pred + 1e-8)).sum(dim=1).mean()
                opt.zero_grad()
                loss.backward()
                opt.step()

                step += 1
                if step % target_sync == 0:
                    target.load_state_dict(net.state_dict())

    # ── 그리디 평가 ──
    cash, shares, holding, entry_val = initial_capital, 0.0, 0, 0.0
    equity_curve, trade_returns = [], []
    net.eval()
    with torch.no_grad():
        for i in range(len(px)):
            if warmup <= i:
                dist = net(torch.tensor(_state_vec(rsi[i], ret_at(i), holding), dtype=torch.float32).unsqueeze(0))
                a = int(q_values(dist).argmax().item())
                if a == 1 and holding == 0:
                    fill = px[i] * (1 + cost)
                    shares, entry_val, cash, holding = cash / fill, cash, 0.0, 1
                elif a == 2 and holding == 1:
                    fill = px[i] * (1 - cost)
                    cash = shares * fill
                    trade_returns.append(cash / entry_val - 1.0)
                    shares, holding = 0.0, 0
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
        "strategy": "c51",
        "episodes": episodes,
        "n_atoms": N_ATOMS,
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return * 100, 4),
        "max_drawdown_pct": round(mdd * 100, 4),
        "sharpe": round(sharpe, 4),
        "win_rate": round(win_rate, 4),
        "num_trades": len(trade_returns),
    }


def c51_backtest_ticker(
    ticker: str,
    days: int = 365,
    episodes: int = 20,
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
    result = c51_backtest(
        closes, episodes=episodes,
        fee_bps=fee_bps, slippage_bps=slippage_bps, initial_capital=initial_capital,
    )
    result["ticker"] = ticker
    result["bars"] = len(closes)
    return result
