"""F1.2 브로커 피드 시험 — 시뮬레이션 틱 + WS 엔드포인트."""
import random
from unittest.mock import patch

from app.services.broker_feed import simulate_tick


def test_simulate_tick_within_bounds():
    rng = random.Random(42)
    prev = 70000.0
    tick = simulate_tick(prev, rng)
    assert tick["source"] == "simulated"
    assert "timestamp" in tick
    # ±0.3% 이내 변동
    assert abs(tick["price"] - prev) / prev <= 0.003 + 1e-9


def test_simulate_tick_deterministic_seed():
    a = simulate_tick(70000.0, random.Random(1))
    b = simulate_tick(70000.0, random.Random(1))
    assert a["price"] == b["price"]


def test_ws_feed_simulated(client):
    """WS /market/feed — 시뮬레이션 틱 수신 (BROKER_WS_URL 미설정)."""
    with patch("app.services.broker_feed._fdr.get_price", return_value={"price": 70000.0}):
        with client.websocket_connect("/market/feed/005930") as ws:
            tick = ws.receive_json()
            assert tick["ticker"] == "005930"
            assert tick["source"] == "simulated"
            assert tick["price"] > 0
