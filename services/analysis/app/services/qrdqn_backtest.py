"""F5 분위수 회귀 DQN — QR-DQN / IQN 백테스팅.

QR-DQN: 행동별 N_QUANT 개 분위수 직접 예측, quantile Huber loss.
IQN: 분위수 τ 를 샘플링해 임베딩(implicit). mode 로 선택.
행동 = argmax mean(quantiles). 시드 결정적.
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

from app.services.backtest import _rsi
from app.services.dqn_backtest import _state_vec

torch.set_num_threads(1)

TRADING_DAYS = 252
ACTIONS = 3
STATE_DIM = 3
N_QUANT = 8
KAPPA = 1.0  # Huber 임계


class _QRNet(nn.Module):
    """상태 → (ACTIONS, N_QUANT) 분위수."""

    def __init__(self, hidden: int = 24) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Linear(STATE_DIM, hidden), nn.ReLU())
        self.head = nn.Linear(hidden, ACTIONS * N_QUANT)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.net(x)).view(-1, ACTIONS, N_QUANT)


class _IQNNet(nn.Module):
    """IQN — 분위수 τ 코사인 임베딩으로 분위수값 생성."""

    def __init__(self, hidden: int = 24, n_cos: int = 16) -> None:
        super().__init__()
        self.n_cos = n_cos
        self.psi = nn.Sequential(nn.Linear(STATE_DIM, hidden), nn.ReLU())
        self.phi = nn.Linear(n_cos, hidden)
        self.head = nn.Linear(hidden, ACTIONS)

    def forward(self, x: torch.Tensor, taus: torch.Tensor) -> torch.Tensor:
        # x (B, STATE_DIM), taus (B, Nq) → (B, Nq, ACTIONS)
        b, nq = taus.shape
        psi = self.psi(x).unsqueeze(1)  # (B,1,hidden)
        i = torch.arange(1, self.n_cos + 1, dtype=torch.float32)
        cos = torch.cos(taus.unsqueeze(-1) * i * np.pi)  # (B,Nq,n_cos)
        phi = torch.relu(self.phi(cos))                  # (B,Nq,hidden)
        h = psi * phi                                    # (B,Nq,hidden)
        return self.head(h)                              # (B,Nq,ACTIONS)


class _FractionNet(nn.Module):
    """상태의존 분위수 비율 — 상태 → N_QUANT 분위수 τ (softmax cumsum 중점)."""

    def __init__(self, n_quant: int, hidden: int = 16) -> None:
        super().__init__()
        self.n_quant = n_quant
        self.net = nn.Sequential(nn.Linear(STATE_DIM, hidden), nn.ReLU(), nn.Linear(hidden, n_quant))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        cum = torch.cumsum(torch.softmax(self.net(x), dim=-1), dim=-1)  # (B,Nq)
        prev = torch.cat([torch.zeros(x.shape[0], 1), cum[:, :-1]], dim=1)
        return (cum + prev) / 2  # 구간 중점 = τ (B,Nq)


def _quantile_huber(td: torch.Tensor, taus: torch.Tensor) -> torch.Tensor:
    """quantile Huber loss. td: (B, Nq_cur, Nq_tgt). taus: (Nq,) 또는 (B,Nq) 상태의존."""
    huber = torch.where(td.abs() <= KAPPA, 0.5 * td.pow(2), KAPPA * (td.abs() - 0.5 * KAPPA))
    if taus.dim() == 1:
        tau_b = taus.view(1, -1, 1)        # (1,Nq_cur,1) → 브로드캐스트
    else:
        tau_b = taus.unsqueeze(-1)         # (B,Nq_cur,1) 상태의존
    weight = (tau_b - (td.detach() < 0).float()).abs()
    return (weight * huber).mean()


def qrdqn_backtest(
    closes: list[float],
    episodes: int = 15,
    gamma: float = 0.95,
    lr: float = 0.01,
    mode: str = "qrdqn",  # qrdqn | iqn | fqf
    cvar_alpha: float = 0.0,  # >0: 하위 분위수 평균(CVaR, risk-sensitive)
    fqf_state_dependent: bool = False,  # FQF 분위수 비율을 상태의존으로
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

    is_iqn = mode in ("iqn", "fqf")
    is_fqf = mode == "fqf"
    sd_fqf = is_fqf and fqf_state_dependent
    # FQF: 분위수 비율(fraction) 학습. 전역 또는 상태의존(FractionNet).
    frac_logits = torch.nn.Parameter(torch.zeros(N_QUANT)) if (is_fqf and not sd_fqf) else None
    frac_net = _FractionNet(N_QUANT) if sd_fqf else None

    def get_taus(states: torch.Tensor | None = None) -> torch.Tensor:
        if sd_fqf and states is not None:
            return frac_net(states)  # (B,Nq) 상태의존
        if is_fqf and not sd_fqf:
            cum = torch.cumsum(torch.softmax(frac_logits, dim=0), dim=0)
            prev = torch.cat([torch.zeros(1), cum[:-1]])
            return (cum + prev) / 2  # 전역 (Nq,)
        return torch.tensor([(2 * j + 1) / (2 * N_QUANT) for j in range(N_QUANT)], dtype=torch.float32)

    net: nn.Module = _IQNNet() if is_iqn else _QRNet()
    target: nn.Module = _IQNNet() if is_iqn else _QRNet()
    target.load_state_dict(net.state_dict())
    target.eval()
    params = list(net.parameters())
    if frac_logits is not None:
        params.append(frac_logits)
    if frac_net is not None:
        params += list(frac_net.parameters())
    opt = torch.optim.Adam(params, lr=lr)

    def q_value(qd: torch.Tensor) -> torch.Tensor:
        """행동가치 — risk-neutral(평균) 또는 CVaR(하위 alpha 분위수 평균)."""
        if cvar_alpha and cvar_alpha > 0.0:
            n_low = max(1, int(np.ceil(cvar_alpha * qd.shape[-1])))
            low, _ = torch.sort(qd, dim=-1)
            return low[..., :n_low].mean(dim=-1)
        return qd.mean(dim=-1)

    def ret_at(i):
        return (px[i] - px[i - 1]) / px[i - 1] if i > 0 else 0.0

    def q_dist(model, states, taus_t):
        """상태배치 → (B, ACTIONS, Nq) 분위수."""
        if is_iqn:
            b = states.shape[0]
            tt = taus_t if taus_t.dim() == 2 else taus_t.unsqueeze(0).expand(b, taus_t.shape[0])
            out = model(states, tt)              # (B,Nq,ACTIONS)
            return out.permute(0, 2, 1)          # (B,ACTIONS,Nq)
        return model(states)

    replay: list = []

    step = 0
    for _ in range(episodes):
        holding, entry = 0, 0.0
        for i in range(warmup, len(px) - 1):
            s_vec = _state_vec(rsi[i], ret_at(i), holding)
            with torch.no_grad():
                s_t = torch.tensor(s_vec, dtype=torch.float32).unsqueeze(0)
                qd = q_dist(net, s_t, get_taus(s_t))
                a = int(q_value(qd).argmax().item())

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

                taus_t = get_taus(ss)  # FQF: grad 흐름(분위수 비율 학습), 상태의존 시 (B,Nq)
                cur = q_dist(net, ss, taus_t)[torch.arange(batch_size), aa]  # (B,Nq)
                with torch.no_grad():
                    taus_n = get_taus(ss2).detach() if sd_fqf else taus_t.detach()
                    nd = q_dist(target, ss2, taus_n)                  # (B,ACTIONS,Nq)
                    na = q_value(nd).argmax(dim=1)
                    nq = nd[torch.arange(batch_size), na]             # (B,Nq)
                    tgt = rr.unsqueeze(1) + gamma * nq                # (B,Nq)
                # pairwise TD: (B, Nq_cur, Nq_tgt)
                td = tgt.unsqueeze(1) - cur.unsqueeze(2)
                loss = _quantile_huber(td, taus_t)
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
        taus_global = get_taus()  # 상태무관 모드용
        for i in range(len(px)):
            if warmup <= i:
                s_t = torch.tensor(_state_vec(rsi[i], ret_at(i), holding), dtype=torch.float32).unsqueeze(0)
                taus_e = get_taus(s_t) if sd_fqf else taus_global
                qd = q_dist(net, s_t, taus_e)
                a = int(q_value(qd).argmax().item())
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
        "strategy": mode,
        "episodes": episodes,
        "n_quantiles": N_QUANT,
        "cvar_alpha": cvar_alpha,
        "fqf_state_dependent": sd_fqf,
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return * 100, 4),
        "max_drawdown_pct": round(mdd * 100, 4),
        "sharpe": round(sharpe, 4),
        "win_rate": round(win_rate, 4),
        "num_trades": len(trade_returns),
    }


def qrdqn_backtest_ticker(
    ticker: str,
    days: int = 365,
    episodes: int = 15,
    mode: str = "qrdqn",
    cvar_alpha: float = 0.0,
    fqf_state_dependent: bool = False,
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
    result = qrdqn_backtest(
        closes, episodes=episodes, mode=mode, cvar_alpha=cvar_alpha,
        fqf_state_dependent=fqf_state_dependent,
        fee_bps=fee_bps, slippage_bps=slippage_bps, initial_capital=initial_capital,
    )
    result["ticker"] = ticker
    result["bars"] = len(closes)
    return result
