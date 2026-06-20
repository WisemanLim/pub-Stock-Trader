"""F5 DQN 백테스팅 — 신경망 Q-learning (PyTorch).

테이블 Q-learning(rl_backtest) 대비 연속 상태 입력. 상태: [rsi_norm, ret_norm, holding].
행동: 0=보유, 1=매수, 2=매도. 경험 리플레이 없이 온라인 학습(경량). 시드 고정 결정적.
torch — 메인 스레드 직접 호출 권장(테스트), HTTP 는 async 엔드포인트.
"""
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from datetime import datetime, timedelta, timezone

import FinanceDataReader as fdr
import numpy as np
import torch
import torch.nn as nn

from app.services.backtest import _rsi

torch.set_num_threads(1)

TRADING_DAYS = 252
ACTIONS = 3
STATE_DIM = 3


class NoisyLinear(nn.Module):
    """Factorized Gaussian NoisyNet 레이어 — 학습 시 파라미터 노이즈로 탐험."""

    def __init__(self, in_dim: int, out_dim: int, sigma0: float = 0.5) -> None:
        super().__init__()
        self.in_dim, self.out_dim = in_dim, out_dim
        self.weight_mu = nn.Parameter(torch.empty(out_dim, in_dim))
        self.weight_sigma = nn.Parameter(torch.empty(out_dim, in_dim))
        self.bias_mu = nn.Parameter(torch.empty(out_dim))
        self.bias_sigma = nn.Parameter(torch.empty(out_dim))
        self.register_buffer("weight_eps", torch.zeros(out_dim, in_dim))
        self.register_buffer("bias_eps", torch.zeros(out_dim))
        bound = 1.0 / (in_dim ** 0.5)
        nn.init.uniform_(self.weight_mu, -bound, bound)
        nn.init.uniform_(self.bias_mu, -bound, bound)
        nn.init.constant_(self.weight_sigma, sigma0 * bound)
        nn.init.constant_(self.bias_sigma, sigma0 * bound)
        self.reset_noise()

    @staticmethod
    def _f(x: torch.Tensor) -> torch.Tensor:
        return x.sign() * x.abs().sqrt()

    def reset_noise(self) -> None:
        ei = self._f(torch.randn(self.in_dim))
        eo = self._f(torch.randn(self.out_dim))
        self.weight_eps.copy_(eo.outer(ei))
        self.bias_eps.copy_(eo)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.training:
            w = self.weight_mu + self.weight_sigma * self.weight_eps
            b = self.bias_mu + self.bias_sigma * self.bias_eps
        else:
            w, b = self.weight_mu, self.bias_mu
        return torch.nn.functional.linear(x, w, b)


class _QNet(nn.Module):
    """Dueling DQN(+옵션 NoisyNet) — Q = V + (A - mean(A))."""

    def __init__(self, hidden: int = 16, noisy: bool = False) -> None:
        super().__init__()
        self.noisy = noisy
        self.feature = nn.Sequential(nn.Linear(STATE_DIM, hidden), nn.ReLU())
        lin = NoisyLinear if noisy else nn.Linear
        self.value = lin(hidden, 1)
        self.advantage = lin(hidden, ACTIONS)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.feature(x)
        v = self.value(h)
        a = self.advantage(h)
        return v + (a - a.mean(dim=-1, keepdim=True))

    def reset_noise(self) -> None:
        if self.noisy:
            self.value.reset_noise()
            self.advantage.reset_noise()


def _state_vec(rsi: float, ret: float, holding: int) -> list[float]:
    r = 0.5 if np.isnan(rsi) else rsi / 100.0
    return [r, float(np.clip(ret, -0.1, 0.1)) * 10.0, float(holding)]


def dqn_backtest(
    closes: list[float],
    episodes: int = 30,
    gamma: float = 0.95,
    epsilon: float = 0.1,
    lr: float = 0.01,
    fee_bps: float = 5.0,
    slippage_bps: float = 5.0,
    initial_capital: float = 10_000_000.0,
    seed: int = 42,
    warmup: int = 15,
    buffer_size: int = 2000,
    batch_size: int = 32,
    target_sync: int = 50,
    epsilon_min: float = 0.01,
    epsilon_decay: float = 0.95,  # 에피소드마다 ε *= decay
    n_step: int = 3,              # n-step 리턴
    per_alpha: float = 0.6,       # PER 우선순위 지수
    noisy: bool = True,           # NoisyNet 탐험
) -> dict:
    if len(closes) < warmup + 5:
        raise ValueError(f"Insufficient data: {len(closes)} < {warmup + 5}")

    torch.manual_seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)

    px = np.asarray(closes, dtype=float)
    rsi = _rsi(px, 14)
    cost = (fee_bps + slippage_bps) / 10_000.0

    qnet = _QNet(noisy=noisy)
    target_net = _QNet(noisy=noisy)
    target_net.load_state_dict(qnet.state_dict())  # 타깃 네트워크 초기 동기화
    target_net.eval()
    opt = torch.optim.Adam(qnet.parameters(), lr=lr)

    from collections import deque
    replay: list = []                    # PER 버퍼 (s,a,R,s_n)
    priorities: list = []                # 우선순위(|TD|^α 비례)
    nbuf: deque = deque(maxlen=n_step)    # n-step 누적 버퍼

    def ret_at(i):
        return (px[i] - px[i - 1]) / px[i - 1] if i > 0 else 0.0

    def push(transition, prio):
        if len(replay) >= buffer_size:
            replay.pop(0)
            priorities.pop(0)
        replay.append(transition)
        priorities.append(prio)

    # ── 학습 (n-step + PER + NoisyNet + Double DQN) ──
    train_step = 0
    eps = epsilon
    max_prio = 1.0
    for _ in range(episodes):
        holding, entry = 0, 0.0
        nbuf.clear()
        for i in range(warmup, len(px) - 1):
            s_vec = _state_vec(rsi[i], ret_at(i), holding)
            qnet.train()
            if noisy:
                qnet.reset_noise()
            with torch.no_grad():
                q_eval = qnet(torch.tensor(s_vec, dtype=torch.float32))
            # NoisyNet 사용 시 ε 탐험 최소화(노이즈가 탐험 담당)
            explore = (not noisy) and (rng.random() < eps)
            a = int(rng.integers(ACTIONS)) if explore else int(torch.argmax(q_eval).item())

            reward = 0.0
            if a == 1 and holding == 0:
                holding, entry = 1, px[i] * (1 + cost)
            elif a == 2 and holding == 1:
                reward = (px[i] * (1 - cost) - entry) / entry
                holding, entry = 0, 0.0
            elif holding == 1:
                reward = ret_at(i + 1)

            s2_vec = _state_vec(rsi[i + 1], ret_at(i + 1), holding)
            nbuf.append((s_vec, a, reward, s2_vec))
            # n-step 리턴 누적 후 push
            if len(nbuf) == n_step:
                R = sum((gamma ** k) * nbuf[k][2] for k in range(n_step))
                s0, a0 = nbuf[0][0], nbuf[0][1]
                sn = nbuf[-1][3]
                push((s0, a0, R, sn), max_prio)

            # PER 미니배치 학습
            if len(replay) >= batch_size:
                pr = np.asarray(priorities, dtype=float) ** per_alpha
                probs = pr / pr.sum()
                idx = rng.choice(len(replay), size=batch_size, replace=False, p=probs)
                batch = [replay[int(j)] for j in idx]
                ss = torch.tensor([b[0] for b in batch], dtype=torch.float32)
                aa = torch.tensor([b[1] for b in batch], dtype=torch.int64)
                rr = torch.tensor([b[2] for b in batch], dtype=torch.float32)
                ssn = torch.tensor([b[3] for b in batch], dtype=torch.float32)

                q_pred = qnet(ss).gather(1, aa.unsqueeze(1)).squeeze(1)
                with torch.no_grad():
                    if noisy:
                        target_net.train()
                        target_net.reset_noise()
                    next_act = qnet(ssn).argmax(dim=1, keepdim=True)  # Double DQN
                    q_next = target_net(ssn).gather(1, next_act).squeeze(1)
                    q_target = rr + (gamma ** n_step) * q_next        # n-step 부트스트랩
                td = q_target - q_pred
                opt.zero_grad()
                (td.pow(2).mean()).backward()
                opt.step()

                # 우선순위 갱신
                new_p = td.detach().abs().numpy() + 1e-5
                for k, j in enumerate(idx):
                    priorities[int(j)] = float(new_p[k])
                max_prio = max(max_prio, float(new_p.max()))

                train_step += 1
                if train_step % target_sync == 0:
                    target_net.load_state_dict(qnet.state_dict())
        eps = max(epsilon_min, eps * epsilon_decay)

    # ── 그리디 평가 ──
    cash, shares, holding, entry_val = initial_capital, 0.0, 0, 0.0
    equity_curve, trade_returns = [], []
    qnet.eval()
    with torch.no_grad():
        for i in range(len(px)):
            if warmup <= i:
                s = torch.tensor(_state_vec(rsi[i], ret_at(i), holding), dtype=torch.float32)
                a = int(torch.argmax(qnet(s)).item())
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
        "strategy": "dqn",
        "episodes": episodes,
        "n_step": n_step,
        "noisy": noisy,
        "per_alpha": per_alpha,
        "epsilon_final": round(eps, 4),
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return * 100, 4),
        "max_drawdown_pct": round(mdd * 100, 4),
        "sharpe": round(sharpe, 4),
        "win_rate": round(win_rate, 4),
        "num_trades": len(trade_returns),
    }


def dqn_backtest_ticker(
    ticker: str,
    days: int = 365,
    episodes: int = 30,
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
    result = dqn_backtest(
        closes, episodes=episodes,
        fee_bps=fee_bps, slippage_bps=slippage_bps, initial_capital=initial_capital,
    )
    result["ticker"] = ticker
    result["bars"] = len(closes)
    return result
