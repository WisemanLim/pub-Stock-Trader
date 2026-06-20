"""F3.3 전략 자가교정 루프 시험 — drift 판정·교정·StrategyMonitor."""
from app.services.self_correction import (
    StrategyMonitor,
    correct_decision,
    detect_drift,
    flip_rate,
)


def test_flip_rate_stable():
    assert flip_rate(["BUY", "BUY", "BUY"]) == 0.0


def test_flip_rate_churn():
    # BUY,SELL,BUY,SELL → 매번 전환 = 1.0
    assert flip_rate(["BUY", "SELL", "BUY", "SELL"]) == 1.0


def test_flip_rate_ignores_hold():
    # HOLD 제외 → BUY,BUY = 전환 0
    assert flip_rate(["BUY", "HOLD", "HOLD", "BUY"]) == 0.0


def test_no_drift_when_stable():
    hist = [{"signal": "BUY", "confidence": 0.8, "weight": 0.2}] * 5
    cand = {"signal": "BUY", "confidence": 0.8, "weight": 0.2}
    d = detect_drift(hist, persona_max=0.3, candidate=cand)
    assert d["drift"] is False
    assert d["reasons"] == []


def test_drift_on_churn():
    hist = [
        {"signal": "BUY", "confidence": 0.8, "weight": 0.2},
        {"signal": "SELL", "confidence": 0.8, "weight": 0.0},
        {"signal": "BUY", "confidence": 0.8, "weight": 0.2},
    ]
    cand = {"signal": "SELL", "confidence": 0.8, "weight": 0.0}
    d = detect_drift(hist, persona_max=0.3, candidate=cand)
    assert d["drift"] is True
    assert any(r.startswith("signal_churn") for r in d["reasons"])


def test_drift_on_low_confidence():
    hist = [{"signal": "HOLD", "confidence": 0.3, "weight": 0.0}] * 4
    cand = {"signal": "HOLD", "confidence": 0.3, "weight": 0.0}
    d = detect_drift(hist, persona_max=0.3, candidate=cand)
    assert d["drift"] is True
    assert any(r.startswith("low_confidence") for r in d["reasons"])


def test_drift_on_weight_breach():
    hist = [{"signal": "BUY", "confidence": 0.8, "weight": 0.2}] * 3
    cand = {"signal": "BUY", "confidence": 0.8, "weight": 0.9}  # 상한 0.3 초과
    d = detect_drift(hist, persona_max=0.3, candidate=cand)
    assert d["drift"] is True
    assert d["weight_breach"] is True


def test_correct_clamps_weight():
    cand = {"signal": "BUY", "confidence": 0.8, "weight": 0.9}
    drift = {"reasons": ["weight_breach(...)"]}
    c = correct_decision(cand, drift, persona_max=0.3)
    assert c["weight"] == 0.3
    assert c["signal"] == "BUY"  # 안정적이면 시그널 유지
    assert "weight_clamped_to_0.3" in c["corrections"]


def test_correct_downgrades_to_hold_on_churn():
    cand = {"signal": "BUY", "confidence": 0.8, "weight": 0.2}
    drift = {"reasons": ["signal_churn(flip_rate=1.0≥0.5)"]}
    c = correct_decision(cand, drift, persona_max=0.3)
    assert c["signal"] == "HOLD"
    assert c["weight"] == 0.0
    assert "downgraded_to_HOLD" in c["corrections"]


def test_no_correction_when_clean():
    cand = {"signal": "BUY", "confidence": 0.8, "weight": 0.2}
    drift = {"reasons": []}
    c = correct_decision(cand, drift, persona_max=0.3)
    assert c["corrected"] is False
    assert c["signal"] == "BUY"


def test_monitor_closes_loop():
    """교정 결과가 이력에 반영 → 다음 평가에 영향(자가교정 폐환)."""
    mon = StrategyMonitor(persona_max=0.3)
    # 불안정 churn 입력 반복 → HOLD 로 수렴
    for sig in ["BUY", "SELL", "BUY", "SELL"]:
        drift, corrected = mon.correct({"signal": sig, "confidence": 0.8, "weight": 0.2})
    # 이후 churn drift 로 HOLD 강등 발생
    assert corrected["signal"] == "HOLD"
    assert len(mon.history()) == 4


def test_monitor_deterministic():
    seq = [{"signal": s, "confidence": 0.8, "weight": 0.2}
           for s in ["BUY", "SELL", "BUY", "SELL"]]
    a = StrategyMonitor(persona_max=0.3)
    b = StrategyMonitor(persona_max=0.3)
    ra = [a.correct(dict(d)) for d in seq]
    rb = [b.correct(dict(d)) for d in seq]
    assert ra == rb


# ── API ──

def test_self_correct_endpoint_clean(client):
    body = {
        "persona": "swing",
        "history": [{"signal": "BUY", "confidence": 0.8, "weight": 0.2}],
        "candidate": {"signal": "BUY", "confidence": 0.8, "weight": 0.2},
    }
    r = client.post("/agents/self_correct", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["drift"]["drift"] is False
    assert data["corrected"]["corrected"] is False


def test_self_correct_endpoint_breach_clamped(client):
    body = {
        "persona": "scalper",  # 상한 0.10
        "history": [],
        "candidate": {"signal": "BUY", "confidence": 0.8, "weight": 0.5},
    }
    r = client.post("/agents/self_correct", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["drift"]["weight_breach"] is True
    assert data["corrected"]["weight"] == 0.10


def test_self_correct_unknown_persona(client):
    body = {"persona": "hodler", "history": [], "candidate": {"signal": "BUY"}}
    r = client.post("/agents/self_correct", json=body)
    assert r.status_code == 400
