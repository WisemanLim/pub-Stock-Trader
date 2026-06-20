"""F5 백테스팅 API — 다전략 + 강화학습."""
from fastapi import APIRouter, HTTPException

from app.schemas.backtest import (
    BacktestRequest,
    BacktestResponse,
    RLBacktestRequest,
    RLBacktestResponse,
)
from app.services.backtest import STRATEGIES, backtest_ticker
from app.services.rl_backtest import rl_backtest_ticker

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/strategies")
def list_strategies() -> dict:
    """지원 전략 목록."""
    return {"strategies": list(STRATEGIES) + ["qlearn", "dqn", "c51", "qrdqn", "iqn", "fqf", "dpg"]}


@router.post("/dpg", response_model=RLBacktestResponse)
async def run_dpg(req: RLBacktestRequest, mode: str = "reinforce",
                  n_rollouts: int = 1, parallel: bool = False, executor: str = "thread") -> RLBacktestResponse:
    """분포형 정책 그라디언트. mode=reinforce|a2c|ppo(GAE), parallel·executor(thread|process)."""
    from app.core.offload import run_training

    try:
        data = await run_training(
            "app.services.dpg_backtest", "dpg_backtest_ticker",
            ticker=req.ticker.upper(),
            days=req.days,
            episodes=req.episodes,
            mode=mode,
            n_rollouts=n_rollouts,
            parallel=parallel,
            executor=executor,
            fee_bps=req.fee_bps,
            slippage_bps=req.slippage_bps,
            initial_capital=req.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RLBacktestResponse(**data)


@router.post("/qrdqn", response_model=RLBacktestResponse)
async def run_qrdqn(req: RLBacktestRequest, mode: str = "qrdqn", cvar_alpha: float = 0.0,
                    fqf_state_dependent: bool = False) -> RLBacktestResponse:
    """분위수 회귀 DQN. mode=qrdqn|iqn|fqf, cvar_alpha>0 risk-sensitive, fqf_state_dependent 상태의존 FQF."""
    from app.core.offload import run_training

    try:
        data = await run_training(
            "app.services.qrdqn_backtest", "qrdqn_backtest_ticker",
            ticker=req.ticker.upper(),
            days=req.days,
            episodes=req.episodes,
            mode=mode,
            cvar_alpha=cvar_alpha,
            fqf_state_dependent=fqf_state_dependent,
            fee_bps=req.fee_bps,
            slippage_bps=req.slippage_bps,
            initial_capital=req.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RLBacktestResponse(**data)


@router.post("/c51", response_model=RLBacktestResponse)
async def run_c51(req: RLBacktestRequest) -> RLBacktestResponse:
    """Distributional DQN(C51) 백테스트. 별도 프로세스 오프로드(이벤트 루프 비블로킹)."""
    from app.core.offload import run_training

    try:
        data = await run_training(
            "app.services.c51_backtest", "c51_backtest_ticker",
            ticker=req.ticker.upper(),
            days=req.days,
            episodes=req.episodes,
            fee_bps=req.fee_bps,
            slippage_bps=req.slippage_bps,
            initial_capital=req.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RLBacktestResponse(**data)


@router.post("/dqn", response_model=RLBacktestResponse)
async def run_dqn(req: RLBacktestRequest) -> RLBacktestResponse:
    """DQN(신경망 Q-learning) 백테스트. 별도 프로세스 오프로드(이벤트 루프 비블로킹)."""
    from app.core.offload import run_training

    try:
        data = await run_training(
            "app.services.dqn_backtest", "dqn_backtest_ticker",
            ticker=req.ticker.upper(),
            days=req.days,
            episodes=req.episodes,
            fee_bps=req.fee_bps,
            slippage_bps=req.slippage_bps,
            initial_capital=req.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RLBacktestResponse(**data)


@router.post("/rl", response_model=RLBacktestResponse)
def run_rl(req: RLBacktestRequest) -> RLBacktestResponse:
    """강화학습(Q-learning) 백테스트 — 학습 후 그리디 정책 평가."""
    try:
        data = rl_backtest_ticker(
            ticker=req.ticker.upper(),
            days=req.days,
            episodes=req.episodes,
            epsilon=req.epsilon,
            fee_bps=req.fee_bps,
            slippage_bps=req.slippage_bps,
            initial_capital=req.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RLBacktestResponse(**data)


@router.post("/", response_model=BacktestResponse)
def run(req: BacktestRequest) -> BacktestResponse:
    """전략 백테스트 — 수수료·슬리피지 반영 성과지표. qlearn은 RL 백테스트로 자동 위임."""
    if req.strategy in ("qlearn", "rl"):
        try:
            data = rl_backtest_ticker(
                ticker=req.ticker.upper(),
                days=req.days,
                episodes=50,
                epsilon=0.1,
                fee_bps=req.fee_bps,
                slippage_bps=req.slippage_bps,
                initial_capital=req.initial_capital,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return BacktestResponse(
            ticker=data["ticker"],
            strategy=data["strategy"],
            bars=data["bars"],
            initial_capital=data["initial_capital"],
            final_equity=data["final_equity"],
            total_return_pct=data["total_return_pct"],
            max_drawdown_pct=data["max_drawdown_pct"],
            sharpe=data["sharpe"],
            sortino=0.0,
            win_rate=data["win_rate"],
            profit_factor=0.0,
            num_trades=data["num_trades"],
        )
    try:
        data = backtest_ticker(
            ticker=req.ticker.upper(),
            days=req.days,
            strategy=req.strategy,
            params=req.params,
            fee_bps=req.fee_bps,
            slippage_bps=req.slippage_bps,
            initial_capital=req.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BacktestResponse(**data)
