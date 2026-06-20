"""Phase B-1+B-3: 시장경보 수집기 + 공매도 통계 시험."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.db import Base, MarketAlertDaily, ShortSellingDaily
from app.services.alert_store import upsert_alerts, get_active_alerts
from app.services.shortsell_store import upsert_short_selling, get_short_selling
from app.services.market_alert_service import KrxMarketAlertService
from app.main import app


# ── in-memory SQLite 격리 ─────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _mem_db(monkeypatch):
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    Sess = sessionmaker(bind=eng, autoflush=False, autocommit=False)

    monkeypatch.setattr("app.db.engine", eng)
    monkeypatch.setattr("app.db.SessionLocal", Sess)
    monkeypatch.setattr("app.services.ohlcv_store.get_session", lambda: Sess())
    monkeypatch.setattr("app.services.alert_store.get_session", lambda: Sess())
    monkeypatch.setattr("app.services.shortsell_store.get_session", lambda: Sess())
    yield
    Base.metadata.drop_all(eng)


# ── DB 스키마 확인 ─────────────────────────────────────────────────────────
class TestDbSchema:
    def test_market_alert_table_exists(self):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(eng)
        assert "market_alert_daily" in inspect(eng).get_table_names()

    def test_short_selling_table_exists(self):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(eng)
        assert "short_selling_daily" in inspect(eng).get_table_names()

    def test_market_alert_columns(self):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(eng)
        cols = {c["name"] for c in inspect(eng).get_columns("market_alert_daily")}
        for name in ("ticker", "date", "level", "name"):
            assert name in cols

    def test_short_selling_columns(self):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(eng)
        cols = {c["name"] for c in inspect(eng).get_columns("short_selling_daily")}
        for name in ("ticker", "date", "short_vol", "short_val", "short_ratio"):
            assert name in cols


# ── alert_store ────────────────────────────────────────────────────────────
SAMPLE_ALERTS = [
    {"ticker": "005930", "name": "삼성전자", "level": "투자주의", "date": "2024-01-10"},
    {"ticker": "000660", "name": "SK하이닉스", "level": "투자경고", "date": "2024-01-10"},
]


class TestAlertStore:
    def test_upsert_alerts_returns_count(self):
        n = upsert_alerts(SAMPLE_ALERTS)
        assert n == 2

    def test_upsert_alerts_empty(self):
        assert upsert_alerts([]) == 0

    def test_upsert_alerts_duplicate_ignored(self):
        upsert_alerts(SAMPLE_ALERTS)
        assert upsert_alerts(SAMPLE_ALERTS) == 0

    def test_upsert_alerts_invalid_date_skipped(self):
        bad = [{"ticker": "005930", "name": "삼성전자", "level": "투자주의", "date": "invalid"}]
        assert upsert_alerts(bad) == 0

    def test_get_active_alerts_all(self):
        upsert_alerts(SAMPLE_ALERTS)
        result = get_active_alerts()
        assert len(result) == 2

    def test_get_active_alerts_by_ticker(self):
        upsert_alerts(SAMPLE_ALERTS)
        result = get_active_alerts("005930")
        assert len(result) == 1
        assert result[0]["level"] == "투자주의"

    def test_get_active_alerts_empty(self):
        assert get_active_alerts("999999") == []

    def test_upsert_alerts_missing_ticker_skipped(self):
        bad = [{"ticker": "", "name": "test", "level": "투자주의", "date": "2024-01-10"}]
        assert upsert_alerts(bad) == 0


# ── shortsell_store ────────────────────────────────────────────────────────
SAMPLE_SHORTSELL = [
    {"date": "2024-01-10", "short_vol": 500_000, "short_val": 35_750_000_000, "short_ratio": 4.5},
    {"date": "2024-01-11", "short_vol": 620_000, "short_val": 44_330_000_000, "short_ratio": 5.2},
]


class TestShortSellStore:
    def test_upsert_returns_count(self):
        n = upsert_short_selling("005930", SAMPLE_SHORTSELL)
        assert n == 2

    def test_upsert_empty(self):
        assert upsert_short_selling("005930", []) == 0

    def test_upsert_duplicate_ignored(self):
        upsert_short_selling("005930", SAMPLE_SHORTSELL)
        assert upsert_short_selling("005930", SAMPLE_SHORTSELL) == 0

    def test_get_short_selling_returns_rows(self):
        upsert_short_selling("005930", SAMPLE_SHORTSELL)
        rows = get_short_selling("005930")
        assert len(rows) == 2
        assert rows[0]["short_ratio"] == 5.2  # 최신 날짜 먼저

    def test_get_short_selling_empty(self):
        assert get_short_selling("999999") == []


# ── KrxMarketAlertService (mock HTTP) ─────────────────────────────────────
class TestMarketAlertService:
    def test_get_alert_stocks_returns_normalized(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "list": [
                {"isuSrtCd": "005930", "isuNm": "삼성전자", "invstWarnTpNm": "투자주의", "invstWarnDd": "20240110"},
                {"isuSrtCd": "000660", "isuNm": "SK하이닉스", "invstWarnTpNm": "투자경고", "invstWarnDd": "20240110"},
            ],
            "totalCount": 2,
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("httpx.post", return_value=mock_resp):
            svc = KrxMarketAlertService()
            result = svc.get_alert_stocks()
        assert len(result) == 2
        assert result[0]["ticker"] == "005930"
        assert result[0]["level"] == "투자주의"
        assert result[0]["date"] == "2024-01-10"

    def test_get_alert_stocks_network_error_returns_empty(self):
        with patch("httpx.post", side_effect=Exception("network error")):
            svc = KrxMarketAlertService()
            result = svc.get_alert_stocks()
        assert result == []

    def test_normalize_date_format(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "list": [{"isuSrtCd": "005930", "isuNm": "삼성", "invstWarnTpNm": "투자위험", "invstWarnDd": "20240115"}],
            "totalCount": 1,
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("httpx.post", return_value=mock_resp):
            result = KrxMarketAlertService().get_alert_stocks()
        assert result[0]["date"] == "2024-01-15"


# ── API 엔드포인트 (store 함수 mock) ──────────────────────────────────────
# worker thread monkeypatch 한계 우회: store 함수를 직접 mock
class TestMarketAlertApi:
    def setup_method(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_get_market_alerts_empty(self):
        with patch("app.api.krx.get_active_alerts", return_value=[]), \
             patch("app.api.krx.upsert_alerts", return_value=0):
            r = self.client.get("/krx/market-alerts")
        assert r.status_code == 200
        data = r.json()
        assert "alerts" in data
        assert data["count"] == 0

    def test_market_alerts_fetch_true_calls_kind(self):
        mock_http = MagicMock()
        mock_http.json.return_value = {"list": [], "totalCount": 0}
        mock_http.raise_for_status = MagicMock()
        with patch("httpx.post", return_value=mock_http), \
             patch("app.api.krx.get_active_alerts", return_value=[]), \
             patch("app.api.krx.upsert_alerts", return_value=0):
            r = self.client.get("/krx/market-alerts?fetch=true")
        assert r.status_code == 200

    def test_sync_endpoint(self):
        mock_http = MagicMock()
        mock_http.json.return_value = {"list": [], "totalCount": 0}
        mock_http.raise_for_status = MagicMock()
        with patch("httpx.post", return_value=mock_http), \
             patch("app.api.krx.upsert_alerts", return_value=0):
            r = self.client.post("/krx/market-alerts/sync")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_get_short_selling_empty(self):
        with patch("app.api.krx.db_short_selling", return_value=[]):
            r = self.client.get("/krx/short-selling/005930")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert data["count"] == 0
