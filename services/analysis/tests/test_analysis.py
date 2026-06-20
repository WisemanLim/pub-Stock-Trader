"""F2 analysis 서비스 시험 — indicators·prediction·screener."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "analysis"


def test_indicators_ok(client, mock_fdr):
    r = client.get("/indicators/005930?days=60")
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "005930"
    assert data["close"] > 0
    assert 0 <= data["rsi"] <= 100
    assert data["macd"] is not None
    assert data["bollinger"]["upper"] > data["bollinger"]["lower"]
    assert data["signal"] in ("BUY", "SELL", "HOLD")


def test_indicators_not_found(client, mock_fdr_empty):
    r = client.get("/indicators/INVALID")
    assert r.status_code == 404


def test_prediction_ok(client, mock_fdr):
    r = client.get("/predict/005930")
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "005930"
    assert data["model"] == "linear-regression-v1"
    assert len(data["horizons"]) == 4
    for h in data["horizons"]:
        assert h["direction"] in ("UP", "DOWN")
        assert 0.0 <= h["confidence"] <= 1.0


def test_prediction_not_found(client, mock_fdr_empty):
    r = client.get("/predict/INVALID")
    assert r.status_code == 404


def test_screener_ok(client, mock_listing):
    r = client.post("/screener/", json={"market": "KRX", "limit": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["market"] == "KRX"
    assert data["total_scanned"] == 3
    assert data["matched"] >= 1
    for res in data["results"]:
        assert res["signal"] in ("BUY", "SELL", "HOLD")


def test_screener_rsi_filter(client, mock_listing):
    r = client.post("/screener/", json={"market": "KRX", "rsi_max": 100, "rsi_min": 0, "limit": 10})
    assert r.status_code == 200
    assert r.json()["matched"] >= 1


def test_openapi_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/indicators/{ticker}" in paths
    assert "/predict/{ticker}" in paths
    assert "/screener/" in paths
    assert "/breadth/" in paths  # C-2


# ── C-1: VWAP / close_pct ────────────────────────────────────────────────────

def test_indicators_vwap_field(client, mock_fdr):
    """C-1: indicators 응답에 vwap_20, close_pct 포함."""
    r = client.get("/indicators/005930")
    assert r.status_code == 200
    data = r.json()
    assert "vwap_20" in data
    assert "close_pct" in data
    # close_pct: 0~1 범위 (고가-저가 내 종가 위치)
    if data["close_pct"] is not None:
        assert 0.0 <= data["close_pct"] <= 1.0


# ── C-2: Market Breadth ──────────────────────────────────────────────────────

def test_breadth_ok(client, mock_listing):
    """C-2: GET /breadth/ → 상승/하락/보합 종목수 + TRIN."""
    r = client.get("/breadth/?market=KOSPI")
    assert r.status_code == 200
    data = r.json()
    assert "advancing" in data
    assert "declining" in data
    assert "unchanged" in data
    assert "trin" in data
    assert "ad_line" in data
    assert data["market"] == "KOSPI"


def test_breadth_unknown_market(client):
    """C-2: 알 수 없는 마켓 → 200 + 빈 데이터(degrade)."""
    r = client.get("/breadth/?market=UNKNOWN")
    assert r.status_code == 200
    data = r.json()
    assert data["sample"] == 0  # 종목 없음


# ── C-5: 스크리너 확장 필터 ─────────────────────────────────────────────────

def test_screener_signal_filter(client, mock_listing):
    """C-5: signal 필터 → 해당 시그널 종목만."""
    r = client.post("/screener/", json={"market": "KRX", "signal": "HOLD", "limit": 10})
    assert r.status_code == 200
    for res in r.json()["results"]:
        assert res["signal"] == "HOLD"


def test_screener_close_range(client, mock_listing):
    """C-5: min_close/max_close 필터."""
    r = client.post("/screener/", json={"market": "KRX", "min_close": 70000.0, "max_close": 80000.0, "limit": 10})
    assert r.status_code == 200
    for res in r.json()["results"]:
        assert 70000.0 <= res["close"] <= 80000.0


def test_screener_limit_cap(client, mock_listing):
    """C-5: limit 상한 80 초과 요청 시 80으로 클리핑."""
    r = client.post("/screener/", json={"market": "KRX", "limit": 200})
    assert r.status_code == 200  # 오류 없음 (내부적으로 min(200, 80) 적용)
