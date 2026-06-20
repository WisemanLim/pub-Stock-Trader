"""F2.2 LSTM(사전학습) + F5 다전략 백테스팅 시험."""
import numpy as np
import pytest

from app.services.backtest import run_backtest


# ── F5 백테스팅 (순수 함수, mock 불요) ──

def test_backtest_sma_uptrend():
    closes = list(np.linspace(10000, 15000, 80) + np.sin(np.arange(80)) * 100)
    r = run_backtest(closes, strategy="sma_cross", params={"short_window": 5, "long_window": 20})
    assert r["strategy"] == "sma_cross"
    assert r["final_equity"] > 0
    assert -100 <= r["max_drawdown_pct"] <= 0
    assert 0.0 <= r["win_rate"] <= 1.0


def test_backtest_rsi_strategy():
    closes = list(np.linspace(10000, 13000, 80) + np.sin(np.arange(80) / 2) * 800)
    r = run_backtest(closes, strategy="rsi_threshold",
                     params={"rsi_period": 14, "rsi_buy_below": 35, "rsi_sell_above": 65})
    assert r["strategy"] == "rsi_threshold"
    assert "sharpe" in r


def test_backtest_macd_strategy():
    closes = list(np.linspace(10000, 14000, 90) + np.sin(np.arange(90) / 3) * 500)
    r = run_backtest(closes, strategy="macd_cross")
    assert r["strategy"] == "macd_cross"
    assert r["num_trades"] >= 0


def test_backtest_unknown_strategy():
    with pytest.raises(ValueError):
        run_backtest(list(np.linspace(100, 200, 60)), strategy="nope")


def test_backtest_insufficient_data():
    with pytest.raises(ValueError):
        run_backtest([100.0, 101.0, 102.0])


def test_backtest_fee_reduces_return():
    closes = list(np.linspace(10000, 13000, 80) + np.sin(np.arange(80) / 2) * 300)
    no_fee = run_backtest(closes, fee_bps=0, slippage_bps=0)
    high_fee = run_backtest(closes, fee_bps=50, slippage_bps=50)
    assert high_fee["final_equity"] <= no_fee["final_equity"] + 1.0


def test_backtest_metrics_keys():
    closes = list(np.linspace(10000, 12000, 60))
    r = run_backtest(closes)
    for k in ["sharpe", "sortino", "win_rate", "profit_factor", "max_drawdown_pct", "num_trades"]:
        assert k in r


def test_backtest_api(client, mock_fdr):
    r = client.post("/backtest/", json={
        "ticker": "005930", "days": 60,
        "strategy": "sma_cross", "params": {"short_window": 5, "long_window": 20},
    })
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "005930"
    assert data["strategy"] == "sma_cross"
    assert data["bars"] == 60


def test_backtest_strategies_endpoint(client):
    r = client.get("/backtest/strategies")
    assert r.status_code == 200
    strategies = r.json()["strategies"]
    assert "sma_cross" in strategies
    assert "rsi_threshold" in strategies
    assert "macd_cross" in strategies


# ── F2.2 LSTM 사전학습 (torch, 메인 스레드 직접 호출) ──

def test_lstm_predict_structure(mock_fdr):
    from app.services.lstm_model import predict_lstm
    data = predict_lstm("005930")
    assert data["model"] == "lstm-v1"
    assert data["weights_source"] in ("checkpoint", "on-the-fly")
    assert len(data["horizons"]) == 4
    for h in data["horizons"]:
        assert h["direction"] in ("UP", "DOWN")
        assert 0.0 <= h["confidence"] <= 1.0
        assert h["predicted_price"] > 0


def test_lstm_train_and_load_checkpoint(mock_fdr, tmp_path, monkeypatch):
    import app.services.lstm_model as lm
    monkeypatch.setattr(lm, "MODEL_DIR", tmp_path)

    info = lm.train_and_save("TESTX", epochs=10)
    assert info["ticker"] == "TESTX"
    assert (tmp_path / "lstm_TESTX.pt").exists()
    assert info["samples"] > 0

    # 체크포인트 로딩 경로 확인
    data = lm.predict_lstm("TESTX")
    assert data["weights_source"] == "checkpoint"


def test_lstm_on_the_fly_when_no_checkpoint(mock_fdr, tmp_path, monkeypatch):
    import app.services.lstm_model as lm
    monkeypatch.setattr(lm, "MODEL_DIR", tmp_path)  # 빈 디렉터리 → 체크포인트 없음
    data = lm.predict_lstm("NOCKPT")
    assert data["weights_source"] == "on-the-fly"


def test_linear_model_label(mock_fdr):
    from app.services.predictor import predict
    assert predict("005930")["model"] == "linear-regression-v1"


# ── 차수5: Transformer + 스케줄 재학습 ──

def test_transformer_predict_structure(mock_fdr):
    from app.services.lstm_model import predict_forecast
    data = predict_forecast("005930", arch="transformer")
    assert data["model"] == "transformer-v1"
    assert len(data["horizons"]) == 4
    for h in data["horizons"]:
        assert h["direction"] in ("UP", "DOWN")
        assert 0.0 <= h["confidence"] <= 1.0


def test_unknown_arch_raises(mock_fdr):
    import pytest
    from app.services.lstm_model import predict_forecast
    with pytest.raises(ValueError):
        predict_forecast("005930", arch="gru")


def test_needs_retrain_when_no_checkpoint(mock_fdr, tmp_path, monkeypatch):
    import app.services.lstm_model as lm
    monkeypatch.setattr(lm, "MODEL_DIR", tmp_path)
    assert lm.needs_retrain("NEW1", "lstm") is True  # 체크포인트 없음


def test_scheduled_retrain_trains_stale(mock_fdr, tmp_path, monkeypatch):
    import app.services.lstm_model as lm
    monkeypatch.setattr(lm, "MODEL_DIR", tmp_path)
    # 최초 → stale(없음) → 재학습
    results = lm.scheduled_retrain(["AAA"], arch="lstm")
    assert results[0]["retrained"] is True
    assert (tmp_path / "lstm_AAA.pt").exists()
    # 재호출 → fresh(방금 학습) → 재학습 안 함
    results2 = lm.scheduled_retrain(["AAA"], arch="lstm", max_age_hours=24.0)
    assert results2[0]["retrained"] is False
    assert results2[0]["reason"] == "fresh"


def test_transformer_checkpoint_roundtrip(mock_fdr, tmp_path, monkeypatch):
    import app.services.lstm_model as lm
    monkeypatch.setattr(lm, "MODEL_DIR", tmp_path)
    info = lm.train_and_save("TFX", arch="transformer", epochs=5)
    assert info["arch"] == "transformer"
    data = lm.predict_forecast("TFX", arch="transformer")
    assert data["weights_source"] == "checkpoint"


# ── 차수5: 강화학습 백테스팅 ──

def test_rl_backtest_structure():
    from app.services.rl_backtest import rl_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = rl_backtest(closes, episodes=20)
    assert r["strategy"] == "qlearn"
    assert r["episodes"] == 20
    assert -100 <= r["max_drawdown_pct"] <= 0
    assert 0.0 <= r["win_rate"] <= 1.0
    assert r["num_trades"] >= 0


def test_rl_backtest_deterministic():
    from app.services.rl_backtest import rl_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = rl_backtest(closes, episodes=15, seed=7)
    b = rl_backtest(closes, episodes=15, seed=7)
    assert a["final_equity"] == b["final_equity"]  # 시드 고정 재현성


def test_rl_backtest_insufficient_data():
    import pytest
    from app.services.rl_backtest import rl_backtest
    with pytest.raises(ValueError):
        rl_backtest([100.0, 101.0], episodes=5)


def test_rl_backtest_api(client, mock_fdr):
    r = client.post("/backtest/rl", json={"ticker": "005930", "days": 60, "episodes": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "005930"
    assert data["strategy"] == "qlearn"
    assert data["bars"] == 60


def test_strategies_includes_qlearn(client):
    r = client.get("/backtest/strategies")
    assert "qlearn" in r.json()["strategies"]


# ── 차수6: 멀티변량 입력 + DQN ──

def test_multivariate_features_exposed(mock_fdr):
    from app.services.lstm_model import predict_forecast
    data = predict_forecast("005930", arch="lstm")
    assert data["features"] == ["close", "volume", "rsi", "macd_hist", "macro", "news"]
    assert len(data["horizons"]) == 4


def test_multivariate_checkpoint_roundtrip(mock_fdr, tmp_path, monkeypatch):
    import app.services.lstm_model as lm
    monkeypatch.setattr(lm, "MODEL_DIR", tmp_path)
    info = lm.train_and_save("MVX", arch="lstm", epochs=5)
    assert info["samples"] > 0
    import torch
    ckpt = torch.load(tmp_path / "lstm_MVX.pt", weights_only=True)
    assert ckpt["n_features"] == 6
    assert ckpt["features"] == ["close", "volume", "rsi", "macd_hist", "macro", "news"]
    # 멀티변량 체크포인트 로딩 예측
    data = lm.predict_forecast("MVX", arch="lstm")
    assert data["weights_source"] == "checkpoint"


def test_channel_providers_injected(mock_fdr):
    import numpy as np
    import app.services.lstm_model as lm
    calls = {"macro": 0, "news": 0}
    seen = {"macro": None, "news": None}

    def macro(ticker, n):
        calls["macro"] += 1
        seen["macro"] = ticker
        return np.linspace(0.0, 1.0, n)

    def news(ticker, n):
        calls["news"] += 1
        seen["news"] = ticker
        return np.full(n, 0.5)

    lm.set_channel_providers(macro=macro, news=news)
    try:
        data = lm.predict_forecast("005930", arch="lstm")
        assert calls["macro"] > 0 and calls["news"] > 0
        # 채널 provider 에 실제 ticker 전달(df.index.name placeholder 버그 회귀 방지).
        assert seen["macro"] == "005930" and seen["news"] == "005930"
        assert len(data["horizons"]) == 4
    finally:
        lm.set_channel_providers(macro=None, news=None)  # 격리 복원


def test_channel_provider_length_mismatch_falls_back(mock_fdr):
    import numpy as np
    import app.services.lstm_model as lm
    lm.set_channel_providers(macro=lambda t, n: np.zeros(n + 5))  # 길이 불일치
    try:
        data = lm.predict_forecast("005930", arch="lstm")  # 중립 폴백 → 정상
        assert data["model"] == "lstm-v1"
    finally:
        lm.set_channel_providers(macro=None, news=None)


def test_dqn_backtest_structure():
    from app.services.dqn_backtest import dqn_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = dqn_backtest(closes, episodes=10)
    assert r["strategy"] == "dqn"
    assert -100 <= r["max_drawdown_pct"] <= 0
    assert 0.0 <= r["win_rate"] <= 1.0


def test_dqn_deterministic():
    from app.services.dqn_backtest import dqn_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = dqn_backtest(closes, episodes=8, seed=11)
    b = dqn_backtest(closes, episodes=8, seed=11)
    assert a["final_equity"] == b["final_equity"]


def test_dqn_insufficient_data():
    import pytest
    from app.services.dqn_backtest import dqn_backtest
    with pytest.raises(ValueError):
        dqn_backtest([100.0, 101.0], episodes=5)


def test_strategies_includes_dqn(client):
    r = client.get("/backtest/strategies")
    assert "dqn" in r.json()["strategies"]


def test_dqn_replay_buffer_params():
    from app.services.dqn_backtest import dqn_backtest
    closes = list(np.linspace(10000, 13000, 150) + np.sin(np.arange(150) / 4) * 700)
    r = dqn_backtest(closes, episodes=8, buffer_size=500, batch_size=16, target_sync=20)
    assert r["strategy"] == "dqn"
    assert 0.0 <= r["win_rate"] <= 1.0
    assert -100 <= r["max_drawdown_pct"] <= 0


def test_dqn_deterministic_with_replay():
    from app.services.dqn_backtest import dqn_backtest
    closes = list(np.linspace(10000, 12000, 120) + np.sin(np.arange(120) / 3) * 400)
    a = dqn_backtest(closes, episodes=6, seed=21, batch_size=16)
    b = dqn_backtest(closes, episodes=6, seed=21, batch_size=16)
    assert a["final_equity"] == b["final_equity"]  # 리플레이 샘플링도 시드 결정적


# ── 차수8: ε 감쇠·Double/Dueling DQN ──

def test_dqn_dueling_network():
    from app.services.dqn_backtest import _QNet
    import torch
    net = _QNet()
    # value + advantage 분리 모듈 존재
    assert hasattr(net, "value") and hasattr(net, "advantage")
    out = net(torch.zeros(4, 3))  # batch=4, state_dim=3
    assert out.shape == (4, 3)    # ACTIONS=3


def test_dqn_epsilon_decay():
    from app.services.dqn_backtest import dqn_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 500)
    r = dqn_backtest(closes, episodes=10, epsilon=0.5, epsilon_decay=0.8, epsilon_min=0.01)
    assert r["epsilon_final"] < 0.5     # 감쇠됨
    assert r["epsilon_final"] >= 0.01   # 하한


def test_dqn_double_deterministic():
    from app.services.dqn_backtest import dqn_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = dqn_backtest(closes, episodes=5, seed=33, batch_size=16)
    b = dqn_backtest(closes, episodes=5, seed=33, batch_size=16)
    assert a["final_equity"] == b["final_equity"]
    assert a["epsilon_final"] == b["epsilon_final"]


# ── 차수9: PER·n-step·NoisyNet DQN ──

def test_noisy_linear_forward():
    from app.services.dqn_backtest import NoisyLinear
    import torch
    layer = NoisyLinear(4, 3)
    layer.train()
    out1 = layer(torch.zeros(1, 4))
    layer.reset_noise()
    out2 = layer(torch.zeros(1, 4))
    assert out1.shape == (1, 3)
    # 학습 모드 + 노이즈 리셋 → 출력 변동(bias 노이즈)
    assert not torch.equal(out1, out2)


def test_dqn_per_nstep_noisy_structure():
    from app.services.dqn_backtest import dqn_backtest
    closes = list(np.linspace(10000, 13000, 150) + np.sin(np.arange(150) / 4) * 700)
    r = dqn_backtest(closes, episodes=6, n_step=3, per_alpha=0.6, noisy=True, batch_size=16)
    assert r["n_step"] == 3
    assert r["noisy"] is True
    assert r["per_alpha"] == 0.6
    assert -100 <= r["max_drawdown_pct"] <= 0


def test_dqn_noisy_deterministic():
    from app.services.dqn_backtest import dqn_backtest
    closes = list(np.linspace(10000, 12000, 120) + np.sin(np.arange(120) / 3) * 400)
    a = dqn_backtest(closes, episodes=5, seed=9, n_step=2, noisy=True, batch_size=16)
    b = dqn_backtest(closes, episodes=5, seed=9, n_step=2, noisy=True, batch_size=16)
    assert a["final_equity"] == b["final_equity"]  # 노이즈도 시드 결정적


# ── 차수10: Distributional C51 ──

def test_c51_structure():
    from app.services.c51_backtest import c51_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = c51_backtest(closes, episodes=4, batch_size=16)
    assert r["strategy"] == "c51"
    assert r["n_atoms"] == 21
    assert -100 <= r["max_drawdown_pct"] <= 0
    assert 0.0 <= r["win_rate"] <= 1.0


def test_c51_deterministic():
    from app.services.c51_backtest import c51_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = c51_backtest(closes, episodes=3, seed=5, batch_size=16)
    b = c51_backtest(closes, episodes=3, seed=5, batch_size=16)
    assert a["final_equity"] == b["final_equity"]


def test_c51_insufficient_data():
    import pytest
    from app.services.c51_backtest import c51_backtest
    with pytest.raises(ValueError):
        c51_backtest([100.0, 101.0], episodes=2)


def test_strategies_includes_c51(client):
    assert "c51" in client.get("/backtest/strategies").json()["strategies"]


# ── 차수11: QR-DQN / IQN ──

def test_qrdqn_structure():
    from app.services.qrdqn_backtest import qrdqn_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = qrdqn_backtest(closes, episodes=4, mode="qrdqn", batch_size=16)
    assert r["strategy"] == "qrdqn"
    assert r["n_quantiles"] == 8
    assert -100 <= r["max_drawdown_pct"] <= 0


def test_iqn_structure():
    from app.services.qrdqn_backtest import qrdqn_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = qrdqn_backtest(closes, episodes=3, mode="iqn", batch_size=16)
    assert r["strategy"] == "iqn"
    assert 0.0 <= r["win_rate"] <= 1.0


def test_qrdqn_deterministic():
    from app.services.qrdqn_backtest import qrdqn_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = qrdqn_backtest(closes, episodes=3, seed=7, batch_size=16)
    b = qrdqn_backtest(closes, episodes=3, seed=7, batch_size=16)
    assert a["final_equity"] == b["final_equity"]


def test_qrdqn_insufficient_data():
    import pytest
    from app.services.qrdqn_backtest import qrdqn_backtest
    with pytest.raises(ValueError):
        qrdqn_backtest([100.0, 101.0], episodes=2)


def test_strategies_includes_qrdqn_iqn(client):
    s = client.get("/backtest/strategies").json()["strategies"]
    assert "qrdqn" in s and "iqn" in s


# ── 차수12: CVaR / FQF ──

def test_cvar_risk_sensitive():
    from app.services.qrdqn_backtest import qrdqn_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 700)
    r = qrdqn_backtest(closes, episodes=4, mode="qrdqn", cvar_alpha=0.25, batch_size=16)
    assert r["cvar_alpha"] == 0.25
    assert -100 <= r["max_drawdown_pct"] <= 0


def test_fqf_structure():
    from app.services.qrdqn_backtest import qrdqn_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = qrdqn_backtest(closes, episodes=3, mode="fqf", batch_size=16)
    assert r["strategy"] == "fqf"
    assert 0.0 <= r["win_rate"] <= 1.0


def test_fqf_deterministic():
    from app.services.qrdqn_backtest import qrdqn_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = qrdqn_backtest(closes, episodes=3, seed=4, mode="fqf", batch_size=16)
    b = qrdqn_backtest(closes, episodes=3, seed=4, mode="fqf", batch_size=16)
    assert a["final_equity"] == b["final_equity"]


def test_strategies_includes_fqf(client):
    assert "fqf" in client.get("/backtest/strategies").json()["strategies"]


# ── 차수13: 상태의존 FQF ──

def test_fqf_state_dependent():
    from app.services.qrdqn_backtest import qrdqn_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = qrdqn_backtest(closes, episodes=3, mode="fqf", fqf_state_dependent=True, batch_size=16)
    assert r["strategy"] == "fqf"
    assert r["fqf_state_dependent"] is True
    assert 0.0 <= r["win_rate"] <= 1.0


def test_fqf_state_dependent_deterministic():
    from app.services.qrdqn_backtest import qrdqn_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = qrdqn_backtest(closes, episodes=3, seed=8, mode="fqf", fqf_state_dependent=True, batch_size=16)
    b = qrdqn_backtest(closes, episodes=3, seed=8, mode="fqf", fqf_state_dependent=True, batch_size=16)
    assert a["final_equity"] == b["final_equity"]


# ── 차수14: 분포형 정책 그라디언트 ──

def test_dpg_structure():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = dpg_backtest(closes, episodes=4)
    assert r["strategy"] == "dpg"
    assert r["n_quantiles"] == 8
    assert -100 <= r["max_drawdown_pct"] <= 0
    assert 0.0 <= r["win_rate"] <= 1.0


def test_dpg_deterministic():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = dpg_backtest(closes, episodes=3, seed=6)
    b = dpg_backtest(closes, episodes=3, seed=6)
    assert a["final_equity"] == b["final_equity"]


def test_dpg_insufficient_data():
    import pytest
    from app.services.dpg_backtest import dpg_backtest
    with pytest.raises(ValueError):
        dpg_backtest([100.0, 101.0], episodes=2)


def test_strategies_includes_dpg(client):
    assert "dpg" in client.get("/backtest/strategies").json()["strategies"]


# ── 차수15: PPO / A2C (GAE) ──

def test_dpg_a2c_gae():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = dpg_backtest(closes, episodes=4, mode="a2c")
    assert r["mode"] == "a2c"
    assert -100 <= r["max_drawdown_pct"] <= 0


def test_dpg_ppo_clip():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = dpg_backtest(closes, episodes=3, mode="ppo", ppo_epochs=3)
    assert r["mode"] == "ppo"
    assert 0.0 <= r["win_rate"] <= 1.0


def test_dpg_ppo_deterministic():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = dpg_backtest(closes, episodes=3, seed=2, mode="ppo")
    b = dpg_backtest(closes, episodes=3, seed=2, mode="ppo")
    assert a["final_equity"] == b["final_equity"]


# ── 차수16: PPO minibatch·엔트로피·KL ──

def test_ppo_minibatch_entropy():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = dpg_backtest(closes, episodes=3, mode="ppo", minibatch=16,
                     entropy_coef=0.02, ppo_epochs=4)
    assert r["mode"] == "ppo"
    assert -100 <= r["max_drawdown_pct"] <= 0


def test_ppo_kl_early_stop():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    # 매우 작은 KL 임계 → 조기종료해도 정상 결과
    r = dpg_backtest(closes, episodes=3, mode="ppo", kl_target=1e-6, ppo_epochs=10)
    assert r["mode"] == "ppo"
    assert 0.0 <= r["win_rate"] <= 1.0


def test_ppo_minibatch_deterministic():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = dpg_backtest(closes, episodes=3, seed=3, mode="ppo", minibatch=16)
    b = dpg_backtest(closes, episodes=3, seed=3, mode="ppo", minibatch=16)
    assert a["final_equity"] == b["final_equity"]


# ── 차수17: 병렬 롤아웃·LR 스케줄 ──

def test_parallel_rollouts():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = dpg_backtest(closes, episodes=3, mode="a2c", n_rollouts=3)
    assert r["n_rollouts"] == 3
    assert -100 <= r["max_drawdown_pct"] <= 0


def test_lr_schedule():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 13000, 120) + np.sin(np.arange(120) / 4) * 600)
    r = dpg_backtest(closes, episodes=5, mode="ppo", lr=0.02, lr_final=0.001)
    assert r["mode"] == "ppo"
    assert 0.0 <= r["win_rate"] <= 1.0


def test_parallel_rollouts_deterministic():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = dpg_backtest(closes, episodes=3, seed=5, mode="a2c", n_rollouts=2)
    b = dpg_backtest(closes, episodes=3, seed=5, mode="a2c", n_rollouts=2)
    assert a["final_equity"] == b["final_equity"]


# ── 차수18: 멀티(스레드) 병렬 롤아웃 ──

def test_parallel_threadpool_matches_sequential():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    seq = dpg_backtest(closes, episodes=3, seed=5, mode="a2c", n_rollouts=3, parallel=False)
    par = dpg_backtest(closes, episodes=3, seed=5, mode="a2c", n_rollouts=3, parallel=True)
    # 롤아웃별 시드 + 순서보존 → 병렬/순차 동일 결과(결정적)
    assert seq["final_equity"] == par["final_equity"]
    assert par["parallel"] is True


def test_parallel_flag_false_when_single_rollout():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    r = dpg_backtest(closes, episodes=2, mode="a2c", n_rollouts=1, parallel=True)
    assert r["parallel"] is False  # 단일 롤아웃 → 병렬 무의미


# ── 차수19: 멀티프로세스(모델 state_dict 복제) 병렬 롤아웃 ──

def test_process_executor_matches_sequential():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    seq = dpg_backtest(closes, episodes=2, seed=5, mode="a2c", n_rollouts=3, parallel=False)
    proc = dpg_backtest(closes, episodes=2, seed=5, mode="a2c", n_rollouts=3,
                        parallel=True, executor="process")
    # 롤아웃별 시드 + state_dict 복제 → 순차와 동일 결과(결정적)
    assert seq["final_equity"] == proc["final_equity"]
    assert proc["executor"] == "process"


def test_executor_field_none_when_not_parallel():
    from app.services.dpg_backtest import dpg_backtest
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    r = dpg_backtest(closes, episodes=2, mode="a2c", n_rollouts=1, parallel=True, executor="process")
    assert r["executor"] == "none"  # 단일 롤아웃 → 병렬 무의미


# ── 차수20: 영속 워커풀(persistent) + 공유메모리(SharedMemory) 텐서 ──

def test_persistent_pool_matches_sequential():
    from app.services.dpg_backtest import dpg_backtest, shutdown_persistent_pool
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    seq = dpg_backtest(closes, episodes=2, seed=5, mode="a2c", n_rollouts=3, parallel=False)
    per = dpg_backtest(closes, episodes=2, seed=5, mode="a2c", n_rollouts=3,
                       parallel=True, executor="persistent")
    # 공유메모리 배열 + 롤아웃별 시드 → 순차와 동일 결과(결정적)
    assert seq["final_equity"] == per["final_equity"]
    assert per["executor"] == "persistent"
    shutdown_persistent_pool()


def test_persistent_pool_reused_across_calls():
    from app.services import dpg_backtest as d
    d.shutdown_persistent_pool()
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    d.dpg_backtest(closes, episodes=2, seed=5, mode="a2c", n_rollouts=2,
                   parallel=True, executor="persistent")
    pool1 = d._PERSIST_POOL
    d.dpg_backtest(closes, episodes=2, seed=5, mode="a2c", n_rollouts=2,
                   parallel=True, executor="persistent")
    pool2 = d._PERSIST_POOL
    assert pool1 is pool2 and pool1 is not None  # 동일 풀 재사용(재생성 없음)
    d.shutdown_persistent_pool()


def test_persistent_matches_process_executor():
    from app.services.dpg_backtest import dpg_backtest, shutdown_persistent_pool
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    proc = dpg_backtest(closes, episodes=2, seed=7, mode="a2c", n_rollouts=3,
                        parallel=True, executor="process")
    per = dpg_backtest(closes, episodes=2, seed=7, mode="a2c", n_rollouts=3,
                       parallel=True, executor="persistent")
    # 동일 코어(_rollout_core) → process·persistent 동일 결과
    assert proc["final_equity"] == per["final_equity"]
    shutdown_persistent_pool()


# ── 차수24: MPM 영속 풀 고도화 — stats·env 워커수·복원력 ──

def test_persistent_pool_stats_lifecycle():
    from app.services import dpg_backtest as d
    d.shutdown_persistent_pool()
    assert d.persistent_pool_stats() == {"active": False, "max_workers": None}
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    d.dpg_backtest(closes, episodes=2, seed=5, mode="a2c", n_rollouts=2,
                   parallel=True, executor="persistent")
    st = d.persistent_pool_stats()
    assert st["active"] is True and st["max_workers"] >= 1
    d.shutdown_persistent_pool()
    assert d.persistent_pool_stats()["active"] is False


def test_persistent_pool_worker_count_from_env(monkeypatch):
    from app.services import dpg_backtest as d
    d.shutdown_persistent_pool()
    monkeypatch.setenv("BACKTEST_PERSIST_WORKERS", "2")
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    d.dpg_backtest(closes, episodes=2, seed=5, mode="a2c", n_rollouts=4,
                   parallel=True, executor="persistent")
    assert d.persistent_pool_stats()["max_workers"] == 2   # env 우선(인자 min(nr,4)=4 무시)
    d.shutdown_persistent_pool()


def test_persistent_map_recreates_after_shutdown():
    from app.services import dpg_backtest as d
    d.shutdown_persistent_pool()
    closes = list(np.linspace(10000, 12000, 100) + np.sin(np.arange(100) / 3) * 400)
    a = d.dpg_backtest(closes, episodes=2, seed=9, mode="a2c", n_rollouts=2,
                       parallel=True, executor="persistent")
    d.shutdown_persistent_pool()                            # 풀 폐기
    b = d.dpg_backtest(closes, episodes=2, seed=9, mode="a2c", n_rollouts=2,
                       parallel=True, executor="persistent")  # 재생성 후 동일 결과
    assert a["final_equity"] == b["final_equity"]
    d.shutdown_persistent_pool()
