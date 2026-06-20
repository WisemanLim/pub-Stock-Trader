"""pytest fixtures — agents 오케스트레이터 (외부 서비스 httpx mock)."""
import pytest
from fastapi.testclient import TestClient


PRICE = {"ticker": "005930", "price": 73500.0, "volume": 1_200_000}

INDICATORS_BUY = {
    "ticker": "005930", "close": 73500.0, "rsi": 25.0,
    "macd": {"macd": 1.0, "signal": 0.5, "histogram": 0.5},
    "atr": 800.0, "signal": "BUY",
    "vwap_20": 73200.0, "close_pct": 0.72,
}

PREDICTION_UP = {
    "ticker": "005930", "current_price": 73500.0, "model": "linear-regression-v1",
    "horizons": [
        {"horizon": "5min", "predicted_price": 73600, "direction": "UP", "confidence": 0.7},
        {"horizon": "1day", "predicted_price": 74000, "direction": "UP", "confidence": 0.65},
    ],
}

FLOW_BUY = {
    "rows": [
        {"institutional_net_vol": 50000, "foreign_net_vol": 30000},
        {"institutional_net_vol": 20000, "foreign_net_vol": 10000},
        {"institutional_net_vol": 5000, "foreign_net_vol": 8000},
    ]
}

ALERT_NONE = {"alerts": [], "count": 0}
ALERT_DANGER = {"alerts": [{"ticker": "005930", "level": "투자위험", "name": ""}], "count": 1}


class FakeResp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def _fake_get(url, timeout=5.0):
    if "/market/price/" in url:
        return FakeResp(PRICE)
    if "/indicators/" in url:
        return FakeResp(INDICATORS_BUY)
    if "/predict/" in url:
        return FakeResp(PREDICTION_UP)
    if "/krx/investor-flow/" in url:
        return FakeResp(FLOW_BUY)
    if "/krx/market-alerts" in url:
        return FakeResp(ALERT_NONE)
    return FakeResp({}, status=404)


def _fake_get_danger(url, timeout=5.0):
    """시장경보 위험 레벨 시나리오."""
    if "/market/price/" in url:
        return FakeResp(PRICE)
    if "/indicators/" in url:
        return FakeResp(INDICATORS_BUY)
    if "/predict/" in url:
        return FakeResp(PREDICTION_UP)
    if "/krx/investor-flow/" in url:
        return FakeResp(FLOW_BUY)
    if "/krx/market-alerts" in url:
        return FakeResp(ALERT_DANGER)
    return FakeResp({}, status=404)


@pytest.fixture
def client(monkeypatch):
    import app.services.orchestrator as orch
    monkeypatch.setattr(orch.httpx, "get", _fake_get)
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_danger(monkeypatch):
    """시장경보 위험(투자위험) 시나리오."""
    import app.services.orchestrator as orch
    monkeypatch.setattr(orch.httpx, "get", _fake_get_danger)
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_degraded(monkeypatch):
    """외부 서비스 전부 실패 → degrade 경로."""
    def _down(url, timeout=5.0):
        raise Exception("connection refused")
    import app.services.orchestrator as orch
    monkeypatch.setattr(orch.httpx, "get", _down)
    from app.main import app
    with TestClient(app) as c:
        yield c
