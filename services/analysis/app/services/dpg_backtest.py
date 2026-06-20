"""F5 분포형 정책 그라디언트(Distributional Policy Gradient) 백테스팅.

정책망 π(a|s)(softmax) + 분포형 critic(상태가치 분위수). REINFORCE with
distributional baseline: advantage = R - E[Z(s)], 정책 그라디언트 + critic 분위수회귀.
행동: 0=보유, 1=매수, 2=매도. 시드 결정적. torch 메인 스레드 직접 호출.
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


class _Policy(nn.Module):
    def __init__(self, hidden: int = 24) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Linear(STATE_DIM, hidden), nn.ReLU(), nn.Linear(hidden, ACTIONS))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.softmax(self.net(x), dim=-1)


class _DistCritic(nn.Module):
    """상태가치 분위수 분포 V(s) → N_QUANT 분위수."""

    def __init__(self, hidden: int = 24) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Linear(STATE_DIM, hidden), nn.ReLU(), nn.Linear(hidden, N_QUANT))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def _rollout_core(state_dict, px, rsi, cost: float, warmup: int, seed: int) -> tuple:
    """단일 롤아웃 공통 코어 — state_dict 복제 정책으로 독립 trajectory 수집.

    px/rsi=np.ndarray(float64). 반환 (states_vecs, acts, rewards). 시드 결정적.
    _process_rollout(피클 리스트)·_shm_rollout(공유메모리) 가 동일 코어를 호출 → 동일 결과 보장.
    """
    torch.manual_seed(seed)
    policy = _Policy()
    policy.load_state_dict(state_dict)
    policy.eval()
    g = torch.Generator()
    g.manual_seed(seed)

    def ret_at(i):
        return (px[i] - px[i - 1]) / px[i - 1] if i > 0 else 0.0

    holding, entry = 0, 0.0
    rewards, states, acts = [], [], []
    for i in range(warmup, len(px) - 1):
        vec = _state_vec(rsi[i], ret_at(i), holding)
        with torch.no_grad():
            a = int(torch.multinomial(policy(torch.tensor(vec, dtype=torch.float32)), 1, generator=g).item())
        states.append(vec)
        acts.append(a)
        reward = 0.0
        if a == 1 and holding == 0:
            holding, entry = 1, px[i] * (1 + cost)
        elif a == 2 and holding == 1:
            reward = (px[i] * (1 - cost) - entry) / entry
            holding, entry = 0, 0.0
        elif holding == 1:
            reward = ret_at(i + 1)
        rewards.append(reward)
    return states, acts, rewards


def _process_rollout(args: tuple) -> tuple:
    """프로세스풀 워커 — policy state_dict 복제로 독립 롤아웃(피클 가능).

    args=(state_dict, px_list, rsi_list, cost, warmup, seed). px/rsi 리스트 피클 전달.
    """
    state_dict, px_list, rsi_list, cost, warmup, seed = args
    px = np.asarray(px_list, dtype=float)
    rsi = np.asarray(rsi_list, dtype=float)
    return _rollout_core(state_dict, px, rsi, cost, warmup, seed)


def _shm_rollout(args: tuple) -> tuple:
    """영속 워커풀 워커 — px/rsi 를 공유메모리(SharedMemory)로 매핑(피클 복사 회피).

    args=(state_dict, px_name, rsi_name, n, cost, warmup, seed). 배열은 read-only 공유,
    state_dict 만 에피소드별 피클. 부모가 unlink 책임(워커는 close 만).
    """
    from multiprocessing import shared_memory

    state_dict, px_name, rsi_name, n, cost, warmup, seed = args
    px_shm = shared_memory.SharedMemory(name=px_name)
    rsi_shm = shared_memory.SharedMemory(name=rsi_name)
    try:
        px = np.ndarray((n,), dtype=np.float64, buffer=px_shm.buf).copy()
        rsi = np.ndarray((n,), dtype=np.float64, buffer=rsi_shm.buf).copy()
        return _rollout_core(state_dict, px, rsi, cost, warmup, seed)
    finally:
        px_shm.close()
        rsi_shm.close()


# 영속 워커풀(MPM) — 에피소드·호출 간 재사용(매 에피소드 풀 재생성 비용 제거).
# offload._executor 와 동일 패턴. 워커수: BACKTEST_PERSIST_WORKERS env > 인자.
_PERSIST_POOL = None
_PERSIST_WORKERS = None  # 현재 풀 워커수(stats)


def _persistent_pool(max_workers: int):
    """프로세스 영속 워커풀(lazy). 워커수=env BACKTEST_PERSIST_WORKERS 우선, 없으면 max_workers."""
    global _PERSIST_POOL, _PERSIST_WORKERS
    if _PERSIST_POOL is None:
        import concurrent.futures as _f
        env = os.getenv("BACKTEST_PERSIST_WORKERS")
        mw = int(env) if (env and env.isdigit() and int(env) > 0) else max_workers
        _PERSIST_POOL = _f.ProcessPoolExecutor(max_workers=mw)
        _PERSIST_WORKERS = mw
    return _PERSIST_POOL


def _persistent_map(fn, tasks: list, max_workers: int) -> list:
    """영속 풀로 map 실행. BrokenProcessPool(워커 사망) 시 풀 1회 재생성 후 재시도(복원력)."""
    from concurrent.futures.process import BrokenProcessPool

    pool = _persistent_pool(max_workers)
    try:
        return list(pool.map(fn, tasks))
    except BrokenProcessPool:
        shutdown_persistent_pool()       # 손상 풀 폐기
        pool = _persistent_pool(max_workers)  # 재생성
        return list(pool.map(fn, tasks))


def persistent_pool_stats() -> dict:
    """영속 풀 상태 — 활성 여부 + 워커수(MPM 조회)."""
    return {"active": _PERSIST_POOL is not None, "max_workers": _PERSIST_WORKERS}


def shutdown_persistent_pool() -> None:
    """영속 워커풀 종료(graceful, 진행 작업 대기). 이후 호출 시 재생성."""
    global _PERSIST_POOL, _PERSIST_WORKERS
    if _PERSIST_POOL is not None:
        _PERSIST_POOL.shutdown(wait=True)
        _PERSIST_POOL = None
        _PERSIST_WORKERS = None


def dpg_backtest(
    closes: list[float],
    episodes: int = 20,
    gamma: float = 0.95,
    lr: float = 0.01,
    mode: str = "reinforce",   # reinforce | a2c | ppo (GAE advantage)
    gae_lambda: float = 0.95,
    ppo_clip: float = 0.2,
    ppo_epochs: int = 4,
    minibatch: int = 0,          # >0: minibatch SGD 크기
    entropy_coef: float = 0.01,  # 엔트로피 보너스 계수
    kl_target: float = 0.02,     # KL 조기종료 임계
    n_rollouts: int = 1,         # 에피소드당 롤아웃 수(분산 감소)
    parallel: bool = False,      # True: 병렬 롤아웃(롤아웃별 시드)
    executor: str = "thread",    # thread | process | persistent(영속풀+공유메모리)
    lr_final: float | None = None,  # 설정 시 lr→lr_final 선형 감쇠
    fee_bps: float = 5.0,
    slippage_bps: float = 5.0,
    initial_capital: float = 10_000_000.0,
    seed: int = 42,
    warmup: int = 15,
) -> dict:
    if len(closes) < warmup + 5:
        raise ValueError(f"Insufficient data: {len(closes)} < {warmup + 5}")

    torch.manual_seed(seed)
    np.random.seed(seed)

    px = np.asarray(closes, dtype=float)
    rsi = _rsi(px, 14)
    cost = (fee_bps + slippage_bps) / 10_000.0
    taus = torch.tensor([(2 * j + 1) / (2 * N_QUANT) for j in range(N_QUANT)], dtype=torch.float32)

    policy = _Policy()
    critic = _DistCritic()
    opt = torch.optim.Adam(list(policy.parameters()) + list(critic.parameters()), lr=lr)

    def ret_at(i):
        return (px[i] - px[i - 1]) / px[i - 1] if i > 0 else 0.0

    gen = torch.Generator()
    gen.manual_seed(seed)

    use_gae = mode in ("a2c", "ppo")

    def rollout(g: torch.Generator):
        """단일 trajectory 수집 → (states, acts, rewards). g=롤아웃 전용 generator."""
        holding, entry = 0, 0.0
        rewards, states, acts = [], [], []
        for i in range(warmup, len(px) - 1):
            s = torch.tensor(_state_vec(rsi[i], ret_at(i), holding), dtype=torch.float32)
            with torch.no_grad():
                probs = policy(s)
                a = int(torch.multinomial(probs, 1, generator=g).item())
            states.append(s)
            acts.append(a)
            reward = 0.0
            if a == 1 and holding == 0:
                holding, entry = 1, px[i] * (1 + cost)
            elif a == 2 and holding == 1:
                reward = (px[i] * (1 - cost) - entry) / entry
                holding, entry = 0, 0.0
            elif holding == 1:
                reward = ret_at(i + 1)
            rewards.append(reward)
        return states, acts, rewards

    nr = max(1, n_rollouts)

    # 영속 워커풀 모드 — px/rsi(에피소드 불변)를 공유메모리에 1회 적재 후 풀 재사용.
    _use_persist = parallel and nr > 1 and executor == "persistent"
    _px_shm = _rsi_shm = None
    if _use_persist:
        from multiprocessing import shared_memory
        _pxf = np.ascontiguousarray(px, dtype=np.float64)
        _rsif = np.ascontiguousarray(rsi, dtype=np.float64)
        _px_shm = shared_memory.SharedMemory(create=True, size=_pxf.nbytes)
        _rsi_shm = shared_memory.SharedMemory(create=True, size=_rsif.nbytes)
        np.ndarray(_pxf.shape, dtype=np.float64, buffer=_px_shm.buf)[:] = _pxf
        np.ndarray(_rsif.shape, dtype=np.float64, buffer=_rsi_shm.buf)[:] = _rsif

    for ep in range(episodes):
        # LR 선형 감쇠
        if lr_final is not None and episodes > 1:
            frac = ep / (episodes - 1)
            cur_lr = lr + (lr_final - lr) * frac
            for pg in opt.param_groups:
                pg["lr"] = cur_lr

        # 롤아웃 수집 — 롤아웃별 시드(결정적). parallel: thread(공유모델) / process(모델 복제) / persistent(영속풀+공유메모리).
        if _use_persist:
            sd = {kk: vv.clone() for kk, vv in policy.state_dict().items()}
            tasks = [(sd, _px_shm.name, _rsi_shm.name, len(px), cost, warmup, seed * 1000 + ep * 100 + r)
                     for r in range(nr)]
            raw = _persistent_map(_shm_rollout, tasks, min(nr, 4))
            rollouts = [([torch.tensor(v, dtype=torch.float32) for v in st], ac, rw) for st, ac, rw in raw]
        elif parallel and nr > 1 and executor == "process":
            import concurrent.futures as _f
            sd = {kk: vv.clone() for kk, vv in policy.state_dict().items()}
            px_list, rsi_list = px.tolist(), rsi.tolist()
            tasks = [(sd, px_list, rsi_list, cost, warmup, seed * 1000 + ep * 100 + r) for r in range(nr)]
            with _f.ProcessPoolExecutor(max_workers=min(nr, 4)) as ex:
                raw = list(ex.map(_process_rollout, tasks))
            # states(list[list]) → 텐서 리스트
            rollouts = [([torch.tensor(v, dtype=torch.float32) for v in st], ac, rw) for st, ac, rw in raw]
        elif parallel and nr > 1:
            import concurrent.futures as _f
            gens = []
            for r in range(nr):
                gg = torch.Generator()
                gg.manual_seed(seed * 1000 + ep * 100 + r)
                gens.append(gg)
            with _f.ThreadPoolExecutor(max_workers=min(nr, 4)) as ex:
                rollouts = list(ex.map(rollout, gens))
        else:
            rollouts = []
            for r in range(nr):
                gg = torch.Generator()
                gg.manual_seed(seed * 1000 + ep * 100 + r)
                rollouts.append(rollout(gg))

        # 각 trajectory 독립 GAE 후 concat(분산 감소)
        all_states, all_acts, all_returns, all_adv = [], [], [], []
        for states, acts, rewards in rollouts:
            returns = []
            acc = 0.0
            for r in reversed(rewards):
                acc = r + gamma * acc
                returns.insert(0, acc)
            ss_r = torch.stack(states)
            rt_r = torch.tensor(returns, dtype=torch.float32)
            with torch.no_grad():
                values = critic(ss_r).mean(dim=1)
                if use_gae:
                    T = len(rewards)
                    adv = torch.zeros(T)
                    gae = 0.0
                    for t in reversed(range(T)):
                        v_next = values[t + 1] if t + 1 < T else 0.0
                        delta = rewards[t] + gamma * float(v_next) - float(values[t])
                        gae = delta + gamma * gae_lambda * gae
                        adv[t] = gae
                    adv_r = adv
                else:
                    adv_r = rt_r - values
            all_states.append(ss_r)
            all_acts.extend(acts)
            all_returns.append(rt_r)
            all_adv.append(adv_r)

        ss = torch.cat(all_states)
        acts_t = torch.tensor(all_acts, dtype=torch.int64)
        returns_t = torch.cat(all_returns)
        advantage = torch.cat(all_adv)
        with torch.no_grad():
            advantage = (advantage - advantage.mean()) / (advantage.std() + 1e-8)
            old_logp = torch.log(policy(ss).gather(1, acts_t.unsqueeze(1)).squeeze(1) + 1e-8)

        n_epochs = ppo_epochs if mode == "ppo" else 1
        n = ss.shape[0]
        mb = minibatch if (mode == "ppo" and minibatch > 0) else n
        stop = False
        for _ in range(n_epochs):
            if stop:
                break
            # minibatch 분할 (시드 결정적 순열)
            perm = torch.randperm(n, generator=gen)
            for start in range(0, n, mb):
                idx = perm[start : start + mb]
                probs_all = policy(ss[idx])
                logp = torch.log(probs_all.gather(1, acts_t[idx].unsqueeze(1)).squeeze(1) + 1e-8)
                if mode == "ppo":
                    ratio = torch.exp(logp - old_logp[idx])
                    clipped = torch.clamp(ratio, 1 - ppo_clip, 1 + ppo_clip)
                    policy_loss = -torch.min(ratio * advantage[idx], clipped * advantage[idx]).mean()
                    entropy = -(probs_all * torch.log(probs_all + 1e-8)).sum(dim=1).mean()
                    policy_loss = policy_loss - entropy_coef * entropy  # 엔트로피 보너스
                else:
                    policy_loss = -(logp * advantage[idx]).mean()
                vdist = critic(ss[idx])
                td = returns_t[idx].unsqueeze(1) - vdist
                huber = torch.where(td.abs() <= 1.0, 0.5 * td.pow(2), td.abs() - 0.5)
                weight = (taus.view(1, -1) - (td.detach() < 0).float()).abs()
                critic_loss = (weight * huber).mean()
                opt.zero_grad()
                (policy_loss + critic_loss).backward()
                opt.step()
            # KL 조기종료 (PPO)
            if mode == "ppo":
                with torch.no_grad():
                    new_logp = torch.log(policy(ss).gather(1, acts_t.unsqueeze(1)).squeeze(1) + 1e-8)
                    kl = (old_logp - new_logp).mean().item()
                if abs(kl) > kl_target:
                    stop = True

    # 공유메모리 해제(부모가 unlink 책임). 풀은 영속 — 종료 안 함.
    if _px_shm is not None:
        _px_shm.close()
        _px_shm.unlink()
        _rsi_shm.close()
        _rsi_shm.unlink()

    # ── 그리디 평가 (argmax 정책) ──
    cash, shares, holding, entry_val = initial_capital, 0.0, 0, 0.0
    equity_curve, trade_returns = [], []
    policy.eval()
    with torch.no_grad():
        for i in range(len(px)):
            if warmup <= i:
                probs = policy(torch.tensor(_state_vec(rsi[i], ret_at(i), holding), dtype=torch.float32))
                a = int(torch.argmax(probs).item())
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
        "strategy": "dpg",
        "mode": mode,
        "n_rollouts": max(1, n_rollouts),
        "parallel": parallel and max(1, n_rollouts) > 1,
        "executor": executor if (parallel and max(1, n_rollouts) > 1) else "none",
        "episodes": episodes,
        "n_quantiles": N_QUANT,
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return * 100, 4),
        "max_drawdown_pct": round(mdd * 100, 4),
        "sharpe": round(sharpe, 4),
        "win_rate": round(win_rate, 4),
        "num_trades": len(trade_returns),
    }


def dpg_backtest_ticker(
    ticker: str,
    days: int = 365,
    episodes: int = 20,
    mode: str = "reinforce",
    n_rollouts: int = 1,
    parallel: bool = False,
    executor: str = "thread",
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
    result = dpg_backtest(
        closes, episodes=episodes, mode=mode, n_rollouts=n_rollouts, parallel=parallel, executor=executor,
        fee_bps=fee_bps, slippage_bps=slippage_bps, initial_capital=initial_capital,
    )
    result["ticker"] = ticker
    result["bars"] = len(closes)
    return result
