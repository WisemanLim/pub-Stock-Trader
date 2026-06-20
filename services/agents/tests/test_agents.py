"""F3.1 멀티에이전트 시험 — 6-에이전트 협업 + degrade (C-3/C-4 포함)."""
import pytest


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "agents"


def test_personas(client):
    r = client.get("/agents/personas")
    assert r.status_code == 200
    data = r.json()
    assert {"scalper", "day", "swing", "position", "scalp", "safe"}.issubset(set(data))
    assert data["scalper"] < data["position"]  # 단기일수록 비중 보수적
    assert data["scalp"] < data["position"]    # scalp(UI) = scalper 동일 상한


def test_analyze_buy_signal(client):
    r = client.post("/agents/analyze", json={"ticker": "005930", "persona": "swing"})
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "005930"
    assert len(data["notes"]) == 6  # C-3/C-4: FlowAgent + AlertAgent 추가
    agents = [n["agent"] for n in data["notes"]]
    assert agents == ["Scraper", "Analyst", "Portfolio", "FlowAgent", "AlertAgent", "Decision"]
    dec = data["decision"]
    assert dec["signal"] == "BUY"          # RSI 25 → 과매도 매수
    assert dec["weight"] > 0               # BUY 면 비중 배정
    assert dec["confidence"] == pytest.approx(0.85)  # 지표·예측 정합(BUY+UP) + C-3 수급 BUY +0.05


def test_analyze_persona_weight_cap(client):
    """scalper 는 swing 보다 비중 상한 낮음."""
    r_scalp = client.post("/agents/analyze", json={"ticker": "005930", "persona": "scalper"})
    r_swing = client.post("/agents/analyze", json={"ticker": "005930", "persona": "swing"})
    w_scalp = r_scalp.json()["decision"]["weight"]
    w_swing = r_swing.json()["decision"]["weight"]
    assert w_scalp < w_swing


def test_analyze_unknown_persona(client):
    r = client.post("/agents/analyze", json={"ticker": "005930", "persona": "hodler"})
    assert r.status_code == 400


def test_flow_agent_note_present(client):
    """C-3: FlowAgent 노트 포함 + 수급 신호 반영."""
    r = client.post("/agents/analyze", json={"ticker": "005930", "persona": "swing"})
    data = r.json()
    flow_note = next(n for n in data["notes"] if n["agent"] == "FlowAgent")
    assert flow_note["data"]["available"] is True
    assert flow_note["data"]["institutional_net"] > 0
    assert flow_note["data"]["signal"] == "BUY"


def test_alert_agent_note_present(client):
    """C-4: AlertAgent 노트 포함 + 정상(경보없음)."""
    r = client.post("/agents/analyze", json={"ticker": "005930", "persona": "swing"})
    data = r.json()
    alert_note = next(n for n in data["notes"] if n["agent"] == "AlertAgent")
    assert alert_note["data"]["alert_level"] == 0
    assert alert_note["data"]["override"] is None


def test_alert_danger_overrides_signal(client_danger):
    """C-4: 투자위험 경보 → 시그널 SELL override."""
    r = client_danger.post("/agents/analyze", json={"ticker": "005930", "persona": "swing"})
    data = r.json()
    assert data["decision"]["signal"] == "SELL"
    alert_note = next(n for n in data["notes"] if n["agent"] == "AlertAgent")
    assert alert_note["data"]["alert_level"] == 3
    assert alert_note["data"]["override"] == "SELL"


def test_analyze_degraded(client_degraded):
    """외부 서비스 장애 시에도 200 + degrade 노트."""
    r = client_degraded.post("/agents/analyze", json={"ticker": "005930", "persona": "swing"})
    assert r.status_code == 200
    data = r.json()
    scraper = next(n for n in data["notes"] if n["agent"] == "Scraper")
    assert "degrade" in scraper["summary"]
    assert data["decision"]["signal"] == "HOLD"  # 데이터 없으면 보수적 HOLD
